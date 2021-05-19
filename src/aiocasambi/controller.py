"""Casambi implementation."""

import logging
import time

from aiohttp import client_exceptions
from asyncio import TimeoutError, sleep

from .errors import (
    LoginRequired,
    ResponseError,
    RateLimit,
    CasambiAPIServerError
)

from .websocket import (
    WSClient,
)
from .consts import (
    SIGNAL_CONNECTION_STATE,
    SIGNAL_DATA,
    STATE_RUNNING,
    SIGNAL_UNIT_PULL_UPDATE
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
        api_key,
        websession,
        wire_id=1,
        user_password=None,
        network_password=None,
        sslcontext=None,
        callback=None,
        network_timeout=300
    ):
        self.email = email
        self.user_password = user_password
        self.network_password = network_password
        self.api_key = api_key
        self.wire_id = wire_id
        self.network_timeout = network_timeout

        self.session = websession

        self.sslcontext = sslcontext
        self.callback = callback

        self.rest_url = 'https://door.casambi.com/v1'

        self.headers = {
            'Content-type': 'application/json',
            'X-Casambi-Key': self.api_key
        }

        self.websocket = None

        self._session_id = None
        self._network_id = None

        self.units = None
        self.scenes = None

        self._reconnecting = False
        self._last_websocket_ping = time.time()

    def get_units(self):
        """ Getter for getting units. """
        return self.units.get_units()

    def get_scenes(self):
        """ Getter for getting scenes. """
        return self.scenes.get_scenes()

    async def create_session(self):
        """ Create Casambi session. """
        if self.user_password:
            await self.create_user_session()

        if self.network_password:
            await self.create_network_session()

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

        LOGGER.debug(f"create_user_session data from request {data}")

        self._session_id = data['sessionId']
        self.headers['X-Casambi-Session'] = self._session_id

        LOGGER.debug(f"user_session_id: {self._session_id}")

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
        self._session_id = data[self._network_id]['sessionId']

        LOGGER.debug(
            f"network_id: {self._network_id} session_id: {self._session_id}")

    async def get_network_information(self):
        """ Creating network information. """
        # GET https://door.casambi.com/v1/networks/{id}

        url = f"{self.rest_url}/networks/{self._network_id}"

        dbg_msg = f"get_network_information request <url: {url} "
        dbg_msg += f"headers= {self.headers}>"
        LOGGER.debug(dbg_msg)

        response = await self.request("get", url=url, headers=self.headers)

        LOGGER.debug(f"get_network_information response: {response}")

        return response

    async def get_network_state(self):
        """ Get network state. """
        # GET https://door.casambi.com/v1/networks/{networkId}/state
        url = f"{self.rest_url}/networks/{self._network_id}/state"

        LOGGER.debug(
            f"get_network_state request url: {url} headers= {self.headers}")

        response = await self.request("get", url=url, headers=self.headers)

        LOGGER.debug(f"get_network_state response: {response}")

        self.units.process_network_state(response)

        self.callback(
            SIGNAL_UNIT_PULL_UPDATE,
            self.units.get_units_unique_ids())

        return response

    async def init_unit_state_controls(self):
        '''
        Getter for getting the unit state from Casambis cloud api
        '''
        # GET https://door.casambi.com/v1/networks/{id}

        for unit_id in self.units.get_units_unique_ids():
            data = await self.get_unit_state_controls(unit_id=unit_id)

            self.units.set_controls(
                unit_id=unit_id,
                data=data)

    def get_unit(self, *, unit_id: int):
        '''
        Get specific unit
        '''
        return self.units.get_unit(unit_id=unit_id)

    async def get_unit_state(self, *, unit_id: int):
        '''
        Getter for getting the unit state from Casambis cloud api
        '''
        # GET https://door.casambi.com/v1/networks/{id}

        url = 'https://door.casambi.com/v1/networks/'
        url += f"{self._network_id}/units/{unit_id}/state"

        response = await self.request("get", url=url, headers=self.headers)

        return response

    async def get_unit_state_controls(self, *, unit_id: int):
        '''
        Get unit controls for unit

        {
            'activeSceneId': 0,
            'address': '26925689c64c',
            'condition': 0,
            'controls': [[{'type': 'Dimmer', 'value': 0.0},
                        {'level': 0.49736842105263157,
                            'max': 6000,
                            'min': 2200,
                            'type': 'CCT',
                            'value': 4090.0}]],
            'dimLevel': 0.0,
            'firmwareVersion': '26.24',
            'fixtureId': 14235,
            'groupId': 0,
            'id': 13,
            'image': 'mbUdKbLz5g3VsVNJIgTYboHa8ce9YfSK',
            'name': 'Arbetslampa',
            'on': True,
            'online': True,
            'position': 9,
            'priority': 3,
            'status': 'ok',
            'type': 'Luminaire'
        }
        '''
        data = await self.get_unit_state(unit_id)

        if 'controls' in data:
            return data['controls']

        return []

    async def initialize(self):
        """Initialiser"""
        network_information = await self.get_network_information()

        self.units = Units(
            network_information['units'],
            controller=self,
            network_id=self._network_id,
            wire_id=self.wire_id
        )

        self.scenes = Scenes(
            network_information['scenes'],
            controller=self,
            network_id=self._network_id,
            wire_id=self.wire_id
        )

        LOGGER.debug(f"network__information: {network_information}")

        # Get initial network state
        self.get_network_state()

        self.init_unit_state_controls()

        return

    async def start_websocket(self):
        """Start websession and websocket to Casambi."""
        dbg_msg = f"start_websocket: api_key: {self.api_key},"
        dbg_msg += f" network_id: {self._network_id},"
        dbg_msg += f" user_session_id: {self._session_id},"
        dbg_msg += f" wire_id: {self.wire_id}"

        LOGGER.debug(dbg_msg)

        self.websocket = WSClient(
            session=self.session,
            ssl_context=self.sslcontext,
            api_key=self.api_key,
            network_id=self._network_id,
            session_id=self._session_id,
            wire_id=self.wire_id,
            controller=self,
            callback=self.session_handler,
        )

        self.websocket.start()

        # We don't want to ping right after we setup a websocket
        self._last_websocket_ping = time.time()

    async def ws_ping(self):
        """ Function for setting a ping over websocket"""
        current_time = time.time()

        if current_time < (self._last_websocket_ping + 60 * 3 + 30):
            # Ping should be sent every 5 min
            msg = 'Not sending websocket ping, '
            msg += f"current_time: {current_time}, "
            msg += f"last websocket ping: {self._last_websocket_ping}"
            LOGGER.debug(msg)
            return

        message = {
            "method": "ping",
            "wire": self.wire_id,
        }

        LOGGER.debug(f"Sending websocket ping: {message}")

        succcess = await self.websocket.send_message(message)

        if not succcess:
            # Try to reconnect
            await self.reconnect()

        self._last_websocket_ping = current_time

    async def ws_send_message(self, msg):
        """ Send websocket message to casambi api"""
        await self.ws_ping()

        LOGGER.debug(f"Sending websocket message: msg {msg}")

        succcess = await self.websocket.send_message(msg)

        if not succcess:
            # Try to reconnect
            await self.reconnect()

    def get_websocket_state(self):
        """ Getter for websocket state """
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
            LOGGER.debug(f"session_handler is handling SIGNAL_DATA: {signal}")
            new_items = self.message_handler(self.websocket.data)

            if new_items and self.callback:
                self.callback(SIGNAL_DATA, new_items)

        elif signal == SIGNAL_CONNECTION_STATE and self.callback:
            dbg_msg = 'session_handler is handling'
            dbg_msg += f"SIGNAL_CONNECTION_STATE: {signal}"
            LOGGER.debug(dbg_msg)

            self.callback(SIGNAL_CONNECTION_STATE, self.websocket.state)
        else:
            LOGGER.debug(f"session_handler is handling signal: {signal}")

    def message_handler(self, message: dict) -> dict:
        """
        Receive event from websocket and identifies where the event belong.
        """
        changes = {}

        LOGGER.debug(f"message_handler recieved websocket message: {message}")

        # Signaling of online gateway
        # {'wire': 9, 'method': 'peerChanged', 'online': True}
        # {'method': 'peerChanged', 'online': False, 'wire': 9}
        #
        # New state
        # {
        #   'condition': 0.0,
        #   'wire': 9,
        #   'activeSceneId': 0,
        #   'controls':
        #   [
        #     {
        #       'type': 'Overheat',
        #        'status': 'ok'
        #     },
        #     {
        #        'type': 'Dimmer',
        #         'value': 0.0
        #     }
        #   ],
        #   'sensors': [],
        #   'method': 'unitChanged',
        #   'online': True,
        #   'details': {
        #     '_name': 'ffff',
        #     'name': 'Name',
        #     'address': 'fffff',
        #     'fixture_model': 'LD220WCM',
        #     'fixture': 859.0,
        #     'OEM': 'Vadsbo'
        #    },
        #    'id': 8,
        #    'priority': 3.0,
        #    'on': True,
        #    'status': 'ok'
        # }
        try:
            if 'method' in message and message['method'] == 'unitChanged':
                changes = self.units.process_unit_event(message)
            elif 'method' in message and message['method'] == 'peerChanged':
                changes = self.units.handle_peer_changed(message)
        except TypeError as err:
            dbg_msg = "message_handler in controller caught TypeError"
            dbg_msg += f" for message: {message} error: {err}"
            LOGGER.debug(dbg_msg)

            raise err
        return changes

    async def check_connection(self):
        """ async function for checking connection """
        if self.get_websocket_state() == STATE_RUNNING:
            return

        # Try to reconnect
        await self.reconnect()

    async def reconnect(self):
        """ async function for reconnecting."""
        LOGGER.debug("Controller is reconnecting")

        if self._reconnecting:
            return

        self._reconnecting = True

        # Trying to reconnect
        reconnect_counter = 0
        while True:
            try:
                reconnect_counter += 1

                dbg_msg = "Controller is trying to reconnect, "
                dbg_msg += f"try: {reconnect_counter}"

                LOGGER.debug(dbg_msg)

                await self.create_session()
            except RateLimit as err:
                LOGGER.debug(
                    f"caught RateLimit exception: {err}, trying again")

                await sleep(self.network_timeout)

                continue
            except client_exceptions.ClientConnectorError:
                dbg_msg = 'caught '
                dbg_msg += 'aiohttp.client_exceptions.ClientConnectorError, '
                dbg_msg += 'trying again'

                LOGGER.debug(dbg_msg)

                await sleep(self.network_timeout)

                continue
            except TimeoutError:
                LOGGER.debug('caught asyncio.TimeoutError, trying again')

                await sleep(self.network_timeout)

                continue

            # Reconnected
            self._reconnecting = False
            break

        await self.start_websocket()

        LOGGER.debug("Controller is reconnected")

    async def turn_unit_on(self, *, unit_id: int):
        '''
        Turn unit on
        '''
        await self.units.turn_unit_on(unit_id=unit_id)

    async def turn_unit_off(self, *, unit_id: int):
        '''
        Turn unit off
        '''
        await self.units.turn_unit_off(unit_id=unit_id)

    def unit_supports_color_temperature(self, *, unit_id: int):
        '''
        Check if unit supports color temperature
        '''
        result = self.units.supports_color_temperature(unit_id=unit_id)

        return result

    def get_supported_color_temperature(self, *, unit_id: int):
        '''
        Get supported color temperatures
        '''
        (min, max, current) = \
            self.units.get_supported_color_temperature(unit_id=unit_id)

        return (min, max, current)

    def unit_supports_brightness(self, *, unit_id: int):
        '''
        Check if unit supports color temperature
        '''
        result = self.units.supports_brightness(unit_id=unit_id)

        return result

    async def set_unit_color_temperature(self, *,
                                         unit_id: int,
                                         value: int,
                                         source="TW"):
        '''
        Set unit color temperature
        '''
        await self.units.set_unit_color_temperature(
            unit_id=unit_id,
            value=value,
            source=source
        )

    async def request(self,
                      method,
                      json=None,
                      url=None,
                      headers=None,
                      **kwargs):
        """Make a request to the API."""
        await self.ws_ping()

        LOGGER.debug(f"request url: {url}")

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
                    raise LoginRequired(
                        f"Call {url} received 401 Unauthorized")

                if res.status == 404:
                    raise ResponseError(f"Call {url} received 404 Not Found")

                if res.status == 410:
                    raise ResponseError(f"Call {url} received 410 Gone")

                if res.status == 429:
                    raise RateLimit(
                        f"Call {url} received 429 Server rate limit exceeded!")

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

        except client_exceptions.ClientError as err:
            raise err
