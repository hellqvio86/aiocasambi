"""Casambi implementation."""

import logging

from pprint import pformat

from aiohttp import client_exceptions

from .errors import raise_error, LoginRequired, ResponseError, RequestError
from .websocket import WSClient, SIGNAL_CONNECTION_STATE, SIGNAL_DATA

from .units import Units
from .scenes import Scenes

LOGGER = logging.getLogger(__name__)



class Controller:
    """Casambi controller."""

    def __init__(
        self,
        *,
        email,
        user_password,
        network_password,
        api_key,
        websession,
        wire_id=1,
        sslcontext=None,
        callback=None,
    ):
        self.email = email
        self.user_password = user_password
        self.network_password = network_password
        self.api_key = api_key
        self.wire_id = wire_id

        self.session = websession


        self.sslcontext = sslcontext
        self.callback = callback

        self.rest_url = 'https://door.casambi.com/v1'

        self.headers =  headers = {
            'Content-type': 'application/json',
            'X-Casambi-Key': self.api_key
        }

        self.websocket = None

        self._user_session_id = None
        self._network_id = None

        self.units = None
        self.scenes = None

    def get_units(self):
        return self.units.get_units()

    def get_scenes(self):
        return self.scenes.get_scenes()

    async def create_user_session(self):
        url = f"{self.rest_url}/users/session"

        headers = {
            'Content-type': 'application/json',
            'X-Casambi-Key': self.api_key
        }

        auth = {
            'email': self.email,
            'password': self.user_password,
        }

        LOGGER.debug(f" headers: {pformat(headers)} auth: {pformat(auth)}")

        data = await self.request("post", url=url, json=auth, headers=headers)

        self._user_session_id = data['sessionId']
        self.headers['X-Casambi-Session'] = self._user_session_id

        LOGGER.debug(f"user_session_id: {self._user_session_id}")


    async def create_network_session(self):
        url = f"{self.rest_url}/networks/session"

        headers = {
            'Content-type': 'application/json',
            'X-Casambi-Key': self.api_key
        }

        auth = {
            "email": self.email,
            "password": self.network_password,
        }

        LOGGER.debug(f"headers: {pformat(headers)} auth: {pformat(auth)}")

        data = await self.request("post", url=url, json=auth, headers=headers)

        self._network_id = list(data.keys())[0]

        LOGGER.debug(f"network_id: {self._network_id}")


    async def get_network_information(self):
        # GET https://door.casambi.com/v1/networks/{id}

        url = f"{self.rest_url}/networks/{self._network_id}"

        LOGGER.debug(f"get_network_information request url: {url} headers= {self.headers}")

        response = await self.request("get", url=url, headers=self.headers)

        LOGGER.debug(f"get_network_information response: {response}")

        return response


    async def initialize(self):
        network_information = await self.get_network_information()

        self.units = Units(network_information['units'], web_sock = self.websocket, network_id=self._network_id, wire_id=self.wire_id)
        self.scenes = Scenes(network_information['scenes'], web_sock = self.websocket, network_id=self._network_id, wire_id=self.wire_id)


        LOGGER.debug(f"network__information: {pformat(network_information)}")

        return

    async def start_websocket(self):
        """Start websession and websocket to Casambi."""
        LOGGER.debug(f"start_websocket: api_key: {self.api_key}, network_id: {self._network_id}, user_session_id: {self._user_session_id} wire_id: {self.wire_id}")
        self.websocket = WSClient(
            session = self.session,
            ssl_context= self.sslcontext,
            api_key = self.api_key,
            network_id = self._network_id,
            user_session_id = self._user_session_id,
            wire_id = self.wire_id,
            callback=self.session_handler,
        )
        self.websocket.start()

    def get_websocket_state(self):
        return self.websocket.state

    def stop_websocket(self) -> None:
        """Close websession and websocket to Casambi."""
        LOGGER.info("Shutting down connections to Casambi.")
        if self.websocket:
            self.websocket.stop()

    def session_handler(self, signal: str) -> None:
        """Signalling from websocket.

           data - new data available for processing.
           state - network state has changed.
        """
        if not self.websocket:
            return

        if signal == SIGNAL_DATA:
            LOGGER.debug(f"SIGNAL_DATA: {signal}")
            new_items = self.message_handler(self.websocket.data)
            if new_items and self.callback:
                self.callback(SIGNAL_DATA, new_items)

        elif signal == SIGNAL_CONNECTION_STATE and self.callback:
            LOGGER.debug(f"SIGNAL_CONNECTION_STATE: {signal}")
            self.callback(SIGNAL_CONNECTION_STATE, self.websocket.state)
        else:
            LOGGER.debug(f"signal: {signal}")


    def message_handler(self, message: dict) -> dict:
        """Receive event from websocket and identifies where the event belong."""
        changes = {}

        LOGGER.debug(f"message: {pformat(message)}")

        if 'method' in message and message['method'] == 'unitChanged':
            changes = self.units.process_unit_event(message)

        return changes


    async def request(self, method, path=None, json=None, url=None, headers=None, **kwargs):
        """Make a request to the API."""

        LOGGER.debug(f"url: {url}")

        try:
            async with self.session.request(
                method,
                url,
                json=json,
                ssl=self.sslcontext,
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

                if res.content_type == "application/json":
                    response = await res.json()

                    return response
                return res

        except client_exceptions.ClientError as err:
            raise RequestError(
                f"Error requesting data from {self.host}: {err}"
            ) from None
