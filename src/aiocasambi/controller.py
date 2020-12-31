"""Casambi implementation."""

import logging

from aiohttp import client_exceptions
from asyncio import TimeoutError, sleep

from .errors import LoginRequired, ResponseError, RateLimit
from .websocket import (
    WSClient,
    SIGNAL_CONNECTION_STATE,
    SIGNAL_DATA,
    STATE_RUNNING
)

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

        self.headers = {
            'Content-type': 'application/json',
            'X-Casambi-Key': self.api_key
        }

        self.websocket = None

        self._user_session_id = None
        self._network_id = None

        self.units = None
        self.scenes = None

        self._reconnecting = False

    def get_units(self):
        """ Getter for getting units. """
        return self.units.get_units()

    def get_scenes(self):
        """ Getter for getting scenes. """
        return self.scenes.get_scenes()

    async def create_user_session(self):
        """ Creating user session. """
        url = f"{self.rest_url}/users/session"

        headers = {
            'Content-type': 'application/json',
            'X-Casambi-Key': self.api_key
        }

        auth = {
            'email': self.email,
            'password': self.user_password,
        }

        LOGGER.debug(f" headers: {headers} auth: {auth}")

        data = await self.request("post", url=url, json=auth, headers=headers)

        LOGGER.debug(f"create_user_session data from request {data} dir(data): {dir(data)}")

        self._user_session_id = data['sessionId']
        self.headers['X-Casambi-Session'] = self._user_session_id

        LOGGER.debug(f"user_session_id: {self._user_session_id}")

    async def create_network_session(self):
        """ Creating network session. """
        url = f"{self.rest_url}/networks/session"

        headers = {
            'Content-type': 'application/json',
            'X-Casambi-Key': self.api_key
        }

        auth = {
            "email": self.email,
            "password": self.network_password,
        }

        LOGGER.debug(f"headers: {headers} auth: {auth}")

        data = await self.request("post", url=url, json=auth, headers=headers)

        LOGGER.debug(f"create_network_session data from request {data}")

        self._network_id = list(data.keys())[0]

        LOGGER.debug(f"network_id: {self._network_id}")

    async def get_network_information(self):
        """ Creating network information. """
        # GET https://door.casambi.com/v1/networks/{id}

        url = f"{self.rest_url}/networks/{self._network_id}"

        LOGGER.debug(f"get_network_information request url: {url} headers= {self.headers}")

        response = await self.request("get", url=url, headers=self.headers)

        LOGGER.debug(f"get_network_information response: {response}")

        return response

    async def get_network_state(self):
        """ Get network state. """
        # GET https://door.casambi.com/v1/networks/{networkId}/state
        url = f"{self.rest_url}/networks/{self._network_id}/state"

        LOGGER.debug(f"get_network_state request url: {url} headers= {self.headers}")

        response = await self.request("get", url=url, headers=self.headers)

        LOGGER.debug(f"get_network_state response: {response}")

        self.units.process_network_state(response)

        return response

    async def initialize(self):
        """Initialiser"""
        network_information = await self.get_network_information()

        self.units = Units(
            network_information['units'],
            web_sock=self.websocket,
            network_id=self._network_id,
            wire_id=self.wire_id
            )

        self.scenes = Scenes(
            network_information['scenes'],
            web_sock=self.websocket,
            network_id=self._network_id,
            wire_id=self.wire_id
            )

        LOGGER.debug(f"network__information: {network_information}")

        # Get initial network state
        self.get_network_state()

        return

    async def start_websocket(self):
        """Start websession and websocket to Casambi."""
        LOGGER.debug(f"start_websocket: api_key: {self.api_key}, network_id: {self._network_id}, user_session_id: {self._user_session_id} wire_id: {self.wire_id}")

        self.websocket = WSClient(
            session=self.session,
            ssl_context=self.sslcontext,
            api_key=self.api_key,
            network_id=self._network_id,
            user_session_id=self._user_session_id,
            wire_id=self.wire_id,
            controller=self,
            callback=self.session_handler,
        )

        self.websocket.start()
    
    async def ws_send_message(self, msg):
        """Send websocket message to casambi api"""
        LOGGER.debug(f"ws_send_message: msg {msg}")

        succcess = await self.websocket.send_message(msg)

        if not succcess:
            # Try to reconnect
            await self.reconnect()

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

        LOGGER.debug(f"message_handler message: {message}")

        # Signaling of online gateway
        # {'wire': 9, 'method': 'peerChanged', 'online': True}
        # {'method': 'peerChanged', 'online': False, 'wire': 9}
        #
        # New state
        # {'condition': 0.0, 'wire': 9, 'activeSceneId': 0, 'controls': [{'type': 'Overheat', 'status': 'ok'}, {'type': 'Dimmer', 'value': 0.0}], 'sensors': [], 'method': 'unitChanged', 'online': True, 'details': {'_name': 'ffff', 'name': 'Name', 'address': 'fffff', 'fixture_model': 'LD220WCM', 'fixture': 859.0, 'OEM': 'Vadsbo'}, 'id': 8, 'priority': 3.0, 'on': True, 'status': 'ok'}
        try:
            if 'method' in message and message['method'] == 'unitChanged':
                changes = self.units.process_unit_event(message)
            elif 'method' in message and message['method'] == 'peerChanged':
                changes = self.units.handle_peer_changed(message)
        except TypeError as err:
            LOGGER.debug(f"caught TypeError in message_handler for message: {message} err: {err}")
            raise err
        return changes

    async def check_connection(self):
        """ async function for checking connection """
        if self.get_websocket_state == STATE_RUNNING:
            return

        # Try to reconnect
        await self.reconnect()

    async def reconnect(self):
        """ async function for reconnecting."""
        timeout = 5 * 60
        LOGGER.debug("Controller is reconnecting")

        if self._reconnecting:
            return

        self._reconnecting = True

        # Trying to reconnect
        reconnect_counter = 0
        while(True):
            try:
                reconnect_counter += 1

                LOGGER.debug(f"Controller is trying to reconnect, try {reconnect_counter}")
                await self.create_user_session()
            except RateLimit as err:
                LOGGER.debug(f"caught RateLimit exception: {err}, trying again")

                await sleep(timeout)

                continue
            except client_exceptions.ClientConnectorError:
                LOGGER.debug("caught aiohttp.client_exceptions.ClientConnectorError, trying again")

                await sleep(timeout)

                continue
            except TimeoutError:
                LOGGER.debug("caught asyncio.TimeoutError, trying again")

                await sleep(timeout)

                continue

            # Reconnected
            self._reconnecting = False
            break

        await self.create_network_session()
        await self.start_websocket()

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

                if res.status == 429:
                    raise RateLimit(f"Call {url} received 429 Server rate limit exceeded!")

                if res.content_type == "application/json":
                    response = await res.json()

                    return response
                return res

        except client_exceptions.ClientError as err:
            raise err
