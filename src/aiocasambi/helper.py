"""
Helper for Casambi

Used for validate credentials
"""

import logging
import aiohttp


from .errors import (
    Unauthorized,
    ResponseError,
    RateLimit,
    CasambiAPIServerError,
    ERROR_CODES,
    get_error,
)

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
        """
        Test user session password
        """
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
        """
        Creating network session.
        """
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
        """
        Make a request to the API.
        """

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

                if res.status in ERROR_CODES:
                    text = await res.text()
                    error = get_error(status_code=res.status)

                    err_msg = f"got status_code: {res.status} text: {text}"
                    LOGGER.error(err_msg)

                    raise error(err_msg)

                if res.content_type == "application/json":
                    response = await res.json()

                    return response

        except aiohttp.client_exceptions.ClientError as err:
            raise err
