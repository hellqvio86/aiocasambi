"""
Helper for Casambi

Used for validate credentials
"""

import logging
import aiohttp


from .errors import LoginRequired, ResponseError, RateLimit, CasambiAPIServerError

LOGGER = logging.getLogger(__name__)


def merge_result(source: dict, destination: dict):
    """
    Merge dicts
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_result(value, node)
        else:
            destination[key] = value

    return destination


class Helper:
    """Casambi helper."""

    def __init__(
        self,
        *,
        email: str,
        api_key: str,
        websession=None,
    ):
        self.email = email
        self.api_key = api_key

        if not websession:
            self.session = aiohttp.ClientSession()
        else:
            self.session = websession

        self.rest_url = "https://door.casambi.com/v1"

        self.headers = {
            "Content-type": "application/json",
            "X-Casambi-Key": self.api_key,
        }

    async def test_user_password(self, *, password: str) -> bool:
        """Test user session password"""
        url = f"{self.rest_url}/users/session"

        headers = {"Content-type": "application/json", "X-Casambi-Key": self.api_key}

        auth = {
            "email": self.email,
            "password": password,
        }

        LOGGER.debug(f" headers: {headers} auth: {auth}")

        data = await self.request("post", url=url, json=auth, headers=headers)

        LOGGER.debug(f"create_user_session data from request {data}")

        return True

    async def test_network_password(self, *, password: str) -> bool:
        """Creating network session."""
        url = f"{self.rest_url}/networks/session"

        headers = {"Content-type": "application/json", "X-Casambi-Key": self.api_key}

        auth = {
            "email": self.email,
            "password": password,
        }

        LOGGER.debug(f"headers: {headers} auth: {auth}")

        data = await self.request("post", url=url, json=auth, headers=headers)

        LOGGER.debug(f"create_network_session data from request {data}")

        return True

    async def request(
        self, method, json=None, url=None, headers=None, **kwargs
    ) -> dict:
        """Make a request to the API."""

        LOGGER.debug(f"request url: {url}")

        try:
            async with self.session.request(
                method,
                url,
                json=json,
                headers=headers,
                **kwargs,
            ) as res:
                LOGGER.debug(f"request: {res.status} {res.content_type} {res}")

                if res.status == 401:
                    raise LoginRequired(f"Call {url} received 401 Unauthorized")

                if res.status == 404:
                    raise ResponseError(f"Call {url} received 404 Not Found")

                if res.status == 410:
                    raise ResponseError(f"Call {url} received 410 Gone")

                if res.status == 429:
                    raise RateLimit(
                        f"Call {url} received 429 Server rate limit exceeded!"
                    )

                if res.status == 500:
                    log_msg = f"Server Error: url: {url} "
                    log_msg += f"headers: {headers} "
                    log_msg += f"status: {res.status} "
                    log_msg += f"response: {res}"
                    raise CasambiAPIServerError(log_msg)

                if res.content_type == "application/json":
                    response = await res.json()

                    return response
                return res

        except aiohttp.client_exceptions.ClientError as err:
            raise err
