"""Casambi implementation."""

import logging
import time
import random

from typing import Tuple
from pprint import pformat
from asyncio import TimeoutError, sleep
from aiohttp import client_exceptions

from .errors import (
    AiocasambiException,
    LoginRequired,
    ResponseError,
    RateLimit,
    CasambiAPIServerError,
)

from .websocket import (
    WSClient,
)
from .consts import (
    SIGNAL_CONNECTION_STATE,
    SIGNAL_DATA,
    STATE_RUNNING,
    SIGNAL_UNIT_PULL_UPDATE,
    MAX_NETWORK_IDS,
)

from .units import Units
from .unit import Unit
from .scenes import Scenes

LOGGER = logging.getLogger(__name__)


class Controller:
    """Casambi controller."""

    def __init__(
        self,
        *,
        email: str,
        api_key: str,
        websession,
        user_password: str = None,
        network_password: str = None,
        sslcontext=None,
        callback=None,
        network_timeout: int = 300,
    ):
        self.email = email
        self.user_password = user_password
        self.network_password = network_password
        self.api_key = api_key
        self.network_timeout = network_timeout

        self.session = websession

        self.sslcontext = sslcontext
        self.callback = callback

        self.rest_url = "https://door.casambi.com/v1"

        self.headers = {
            "Content-type": "application/json",
            "X-Casambi-Key": self.api_key,
        }

        self.websocket = {}

        self._session_ids = {}
        self._network_ids = set()

        self.units = {}
        self.scenes = {}
        self._wire_id_to_network_id = {}

        self._reconnecting = False
        self._last_websocket_ping = time.time()

    def set_session_id(self, *, session_id: str) -> None:
        """Set session id"""
        self.headers["X-Casambi-Session"] = session_id

    def get_units(self, *, network_id: str) -> list:
        """Getter for getting units."""
        return self.units[network_id].get_units()

    def get_scenes(self) -> list:
        """Getter for getting scenes."""
        return self.scenes.get_scenes()

    async def create_session(self) -> None:
        LOGGER.debug("Create session called!")

        """Create Casambi session."""
        if self.user_password:
            LOGGER.debug("Creating user session")
            await self.create_user_session()

        if self.network_password:
            LOGGER.debug("Creating network session")
            await self.create_network_session()

    async def create_user_session(self) -> None:
        """
        Creating user session.

        Expected response:
        {
            "sessionId": "hJK65SenmlL2354y.P822D76HufewNSloo780PvU-78DwdmnMA8exzIo9.mmNWD23whEqbPOsl11hjjWo03___",
            "sites": {
                "Rg5alx4BF41lSU2jK4r7T0Q7X0i00mQ": {
                    "name": "Playground",
                    "address": "",
                    "role": "ADMIN",
                    "networks": {
                        "VcrTwqLZJ26UYMXxTClmpfZxELcrPUAa": {
                            "id": "VcrTwqLZJ26UYMXxTClmpfZxELcrPUAa",
                            "address": "a00f251f77cc",
                            "name": "Dev Network",
                            "type": "OPEN",
                            "grade": "EVOLUTION",
                            "role": "ADMIN"
                        }
                    }
                }
            },
            "networks": {
                "VcrTwqLZJ26UYMXxTClmpfZxELcrPUAa": {
                    "id": "VcrTwqLZJ26UYMXxTClmpfZxELcrPUAa",
                    "address": "a00f251f77cc",
                    "name": "Dev Network",
                    "type": "OPEN",
                    "grade": "EVOLUTION",
                    "role": "ADMIN"
                }
            }
        }
        """
        url = f"{self.rest_url}/users/session"

        headers = {"Content-type": "application/json", "X-Casambi-Key": self.api_key}

        auth = {
            "email": self.email,
            "password": self.user_password,
        }

        LOGGER.debug(f" headers: {pformat(headers)} auth: {pformat(auth)}")

        data = None
        try:
            data = await self.request("post", url=url, json=auth, headers=headers)
        except LoginRequired as err:
            LOGGER.error("create_user_session caught LoginRequired exception")
            raise err

        LOGGER.debug(f"create_user_session data from request {data}")

        self.set_session_id(session_id=data["sessionId"])

        for network_key in data["networks"].keys():
            self._network_ids.add(data["networks"][network_key]["id"])

            if "sessionId" in data["networks"][network_key]:
                self._session_ids[network_key] = data["networks"][network_key][
                    "sessionId"
                ]
            else:
                self._session_ids[network_key] = data["sessionId"]

        LOGGER.debug(
            f"network_ids: {pformat(self._network_ids)} session_ids: {pformat(self._session_ids)}"
        )

    async def create_network_session(self) -> None:
        """
        Creating network session.

        Expected response:
        {
            'VcrTwqLZJ26UYMXxTClmpfZxELcrPUAa': {
                'address': 'ff69cc2fdf00',
                'grade': 'CLASSIC',
                'id': 'VcrTwqLZJ26UYMXxTClmpfZxELcrPUAa',
                'mac': 'ff69cc2fdf00',
                'name': 'Dev Network',
                'sessionId': '5ARffxyrpwJYy7Hf1xxx-HmF18Agmff39kSKDxxBxxxWkUg59SU9pii.9jBVi6PEyfq9Y9gokiel0yfljGmJQg__',
                'type': 'PROTECTED'
                },
            'TYqGffRLwKrArqkOQVtXcw1ffgdLIjkU': {
                'address': 'ffcaaaacbb51',
                'grade': 'EVOLUTION',
                'id': 'TYqGffRLwKrArqkOQVtXcw1ffgdLIjkU',
                'mac': 'ffcaaaacbb51',
                'name': 'Dev Network',
                'sessionId': 'KDRmwOqerOsTyrr0x9HLrGFe1nknEk3oRoT-Kz3DJ.wx97MTXQXC.ZbWwqt9ze0KwC6h3GCTlPsUemX8uvK5Ow__',
                'type': 'PROTECTED'}
        }
        """
        url = f"{self.rest_url}/networks/session"

        headers = {"Content-type": "application/json", "X-Casambi-Key": self.api_key}

        auth = {
            "email": self.email,
            "password": self.network_password,
        }

        LOGGER.debug(f"headers: {headers} auth: {auth}")

        data = None
        try:
            data = await self.request("post", url=url, json=auth, headers=headers)
        except LoginRequired as err:
            LOGGER.error("create_network_session caught LoginRequired exception")
            raise err

        LOGGER.debug(f"create_network_session data from request {pformat(data)}")

        for network_id in data.keys():
            self._network_ids.add(data[network_id]["id"])
            self._session_ids[network_id] = data[network_id]["sessionId"]

        LOGGER.debug(
            f"network_ids: {pformat(self._network_ids)} session_ids: {pformat(self._session_ids)}"
        )

    async def get_network_information(self) -> dict:
        """Creating network information."""
        # GET https://door.casambi.com/v1/networks/{id}
        result = {}

        if not self._network_ids or len(self._network_ids) == 0:
            raise AiocasambiException("Network ids not set")

        for network_id in self._network_ids:
            self.set_session_id(session_id=self._session_ids[network_id])
            url = f"{self.rest_url}/networks/{network_id}"

            dbg_msg = f"get_network_information request <url: {url} "
            dbg_msg += f"headers= {self.headers}>"
            LOGGER.debug(dbg_msg)

            data = None
            try:
                data = await self.request("get", url=url, headers=self.headers)
            except LoginRequired as err:
                LOGGER.error("get_network_information caught LoginRequired exception")
                raise err

            LOGGER.debug(f"get_network_information response: {pformat(data)}")
            result[network_id] = data

        return result

    async def get_network_state(self) -> dict:
        """Get network state."""
        # GET https://door.casambi.com/v1/networks/{networkId}/state
        result = []

        if not self._network_ids or len(self._network_ids) == 0:
            raise AiocasambiException("Network ids not set")

        LOGGER.debug(f"get_network_state units: {pformat(self.units)}")

        for network_id in self._network_ids:
            self.set_session_id(session_id=self._session_ids[network_id])
            url = f"{self.rest_url}/networks/{network_id}/state"

            LOGGER.debug(
                f"get_network_state request url: {url} headers= {self.headers}"
            )

            data = None
            try:
                data = await self.request("get", url=url, headers=self.headers)
            except LoginRequired as err:
                LOGGER.error("get_network_state caught LoginRequired exception")
                raise err

            LOGGER.debug(f"get_network_state response: {data}")

            self.units[network_id].process_network_state(data)

            self.callback(
                SIGNAL_UNIT_PULL_UPDATE, self.units[network_id].get_units_unique_ids()
            )

            result.append(data)

        return result

    async def init_unit_state_controls(self, *, network_id: str) -> None:
        """
        Getter for getting the unit state from Casambis cloud api
        """
        # GET https://door.casambi.com/v1/networks/{id}

        for unit_id in self.units[network_id].get_units_unique_ids():
            data = await self.get_unit_state_controls(
                unit_id=unit_id, network_id=network_id
            )

            self.self.units[network_id].set_controls(unit_id=unit_id, data=data)

    def get_unit(self, *, unit_id: int, network_id: str) -> Unit:
        """
        Get specific unit
        """
        return self.units.get_unit(unit_id=unit_id)

    def get_unit_value(self, *, unit_id: int, network_id: str) -> int:
        """
        Get the unit value
        """
        return self.units.get_unit_value(unit_id=unit_id)

    def get_unit_distribution(self, *, unit_id: int, network_id: str) -> int:
        """
        Get the unit distribution
        """
        return self.units.get_unit_distribution(unit_id=unit_id)

    async def get_unit_state(self, *, unit_id: int, network_id: str) -> dict:
        """
        Getter for getting the unit state from Casambis cloud api
        """
        # GET https://door.casambi.com/v1/networks/{id}

        if not self._network_ids or len(self._network_ids) == 0:
            raise AiocasambiException("Network ids not set")

        self.set_session_id(session_id=self._session_ids[network_id])

        url = "https://door.casambi.com/v1/networks/"
        url += f"{network_id}/units/{unit_id}/state"

        data = None
        try:
            data = await self.request("get", url=url, headers=self.headers)
        except LoginRequired as err:
            LOGGER.error("get_unit_state caught LoginRequired exception")
            raise err

        return data

    async def get_unit_state_controls(self, *, unit_id: int, network_id: str) -> list:
        """
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
        """
        data = await self.get_unit_state(unit_id=unit_id, network_id=network_id)

        if "controls" in data:
            return data["controls"]

        return []

    async def initialize(self) -> None:
        """Initialiser"""
        network_information = await self.get_network_information()

        for network_id, data in network_information.items():
            self.units = Units(
                data["units"],
                controller=self,
                network_id=network_id,
                wire_id=0,
            )

            self.scenes = Scenes(
                data["scenes"],
                controller=self,
                network_id=network_id,
                wire_id=0,
            )

        LOGGER.debug(f"network__information: {pformat(network_information)}")

        # Get initial network state
        await self.get_network_state()

        for network_id, _ in network_information.items():
            await self.init_unit_state_controls(network_id=network_id)

        return

    async def start_websockets(self) -> None:
        """
        Start websocket for all networks
        """
        for network_id in self._network_ids:
            await self.start_websocket(network_id=network_id)

    async def start_websocket(self, *, network_id: str) -> None:
        """
        Start websession and websocket to Casambi.
        """
        wire_id = random.randint(1, MAX_NETWORK_IDS)

        while wire_id not in self._wire_id_to_network_id:
            wire_id = random.randint(1, MAX_NETWORK_IDS)

        self._wire_id_to_network_id[wire_id] = network_id

        session_id = self._session_ids[network_id]

        dbg_msg = f"start_websocket: api_key: {self.api_key},"
        dbg_msg += f" network_id: {network_id},"
        dbg_msg += f" user_session_id: {session_id},"
        dbg_msg += f" wire_id: {wire_id}"

        LOGGER.debug(dbg_msg)

        self.websocket[network_id] = WSClient(
            session=self.session,
            ssl_context=self.sslcontext,
            api_key=self.api_key,
            network_id=network_id,
            session_id=session_id,
            wire_id=wire_id,
            controller=self,
            callback=self.session_handler,
        )

        self.websocket[network_id].start()

        # We don't want to ping right after we setup a websocket
        self._last_websocket_ping = time.time()

        # Set wire_id
        self.set_wire_id(wire_id=wire_id, network_id=network_id)

    async def ws_ping(self) -> None:
        """Function for setting a ping over websocket"""
        current_time = time.time()

        if current_time < (self._last_websocket_ping + 60 * 3 + 30):
            # Ping should be sent every 5 min
            msg = "Not sending websocket ping, "
            msg += f"current_time: {current_time}, "
            msg += f"last websocket ping: {self._last_websocket_ping}"
            LOGGER.debug(msg)
            return

        for wire_id, network_id in self._wire_id_to_network_id.items():
            message = {
                "method": "ping",
                "wire": wire_id,
            }

            LOGGER.debug(f"Sending websocket ping: {message}")

            succcess = await self.websocket[network_id].send_message(message)

            if not succcess:
                # Try to reconnect
                await self.reconnect()

        self._last_websocket_ping = current_time

    async def ws_send_message(self, msg: dict, network_id: str) -> None:
        """Send websocket message to casambi api"""
        await self.ws_ping()

        LOGGER.debug(f"Sending websocket message: msg {msg}")

        succcess = await self.websocket[network_id].send_message(msg)

        if not succcess:
            # Try to reconnect
            await self.reconnect()

    def get_websocket_state(self, *, network_id: str) -> str:
        """Getter for websocket state"""
        return self.websocket[network_id].state

    async def stop_websockets(self) -> None:
        """Close websession and websocket to Casambi."""

        LOGGER.info("Shutting down connections to Casambi.")

        for network_id, _ in self.websocket.items():
            await self.stop_websocket(network_id=network_id)

    async def stop_websocket(self, *, network_id: str) -> None:
        """Close websession and websocket to Casambi."""

        LOGGER.info("Shutting down connections to Casambi.")

        if network_id in self.websocket:
            self.websocket[network_id].stop()

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
        else:
            LOGGER.debug(f"session_handler is NOT handling signal: {signal}")

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
        wire_id = message["wire"]
        network_id = self._wire_id_to_network_id[wire_id]

        try:
            if "method" in message and message["method"] == "unitChanged":
                changes = self.units[network_id].process_unit_event(message)
            elif "method" in message and message["method"] == "peerChanged":
                changes = self.units[network_id].handle_peer_changed(message)
        except TypeError as err:
            dbg_msg = "message_handler in controller caught TypeError"
            dbg_msg += f" for message: {message} error: {err}"
            LOGGER.debug(dbg_msg)

            raise err
        return changes

    async def check_connection(self) -> None:
        """async function for checking connection"""
        if self.get_websocket_state() == STATE_RUNNING:
            return

        # Try to reconnect
        await self.reconnect()

    async def reconnect(self) -> None:
        """async function for reconnecting."""
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
                LOGGER.debug(f"caught RateLimit exception: {err}, trying again")

                await sleep(self.network_timeout)

                continue
            except client_exceptions.ClientConnectorError:
                dbg_msg = "caught "
                dbg_msg += "aiohttp.client_exceptions.ClientConnectorError, "
                dbg_msg += "trying again"

                LOGGER.debug(dbg_msg)

                await sleep(self.network_timeout)

                continue
            except TimeoutError:
                LOGGER.debug("caught asyncio.TimeoutError, trying again")

                await sleep(self.network_timeout)

                continue

            # Reconnected
            self._reconnecting = False
            break

        # Set new session ids for websocket
        for network_id in self.websocket.keys():
            self.websocket[network_id].session_id = self._session_ids[network_id]
        LOGGER.debug("Controller is reconnected")

    async def turn_unit_on(self, *, unit_id: int, network_id: str) -> None:
        """
        Turn unit on
        """
        await self.units[network_id].turn_unit_on(unit_id=unit_id)

    async def turn_unit_off(self, *, unit_id: int, network_id: str) -> None:
        """
        Turn unit off
        """
        await self.units[network_id].turn_unit_off(unit_id=unit_id)

    def unit_supports_rgb(self, *, unit_id: int, network_id: str) -> bool:
        """
        Check if unit supports rgb
        """
        result = self.units[network_id].supports_rgb(unit_id=unit_id)

        return result

    def unit_supports_rgbw(self, *, unit_id: int, network_id: str) -> bool:
        """
        Check if unit supports color rgbw
        """
        result = self.units[network_id].supports_rgbw(unit_id=unit_id)

        return result

    def unit_supports_color_temperature(self, *, unit_id: int, network_id: str) -> bool:
        """
        Check if unit supports color temperature
        """
        result = self.units[network_id].supports_color_temperature(unit_id=unit_id)

        return result

    def get_supported_color_temperature(
        self, *, unit_id: int, network_id: str
    ) -> Tuple[int, int, int]:
        """
        Get supported color temperatures
        """
        (cct_min, cct_max, current) = self.units[
            network_id
        ].get_supported_color_temperature(unit_id=unit_id)

        return (cct_min, cct_max, current)

    def unit_supports_brightness(self, *, unit_id: int, network_id: str) -> bool:
        """
        Check if unit supports color temperature
        """
        result = self.units[network_id].supports_brightness(unit_id=unit_id)

        return result

    def unit_supports_distribution(self, *, unit_id: int, network_id: str) -> bool:
        """
        Check if unit supports distribution
        """
        result = self.units[network_id].supports_distribution(unit_id=unit_id)

        return result

    def set_wire_id(self, *, wire_id: int, network_id: str) -> None:
        self.units[network_id].set_wire_id(wire_id=wire_id)
        self.scenes[network_id].set_wire_id(wire_id=wire_id)

    async def set_unit_rgbw(
        self,
        *,
        unit_id: int,
        network_id: str,
        color_value: Tuple[int, int, int, int],
        send_rgb_format=False,
    ) -> None:
        """
        Set unit color temperature
        """
        await self.units[network_id].set_unit_rgbw(
            unit_id=unit_id,
            color_value=color_value,
        )

    async def set_unit_rgb(
        self,
        *,
        unit_id: int,
        network_id: str,
        color_value: Tuple[int, int, int],
        send_rgb_format=False,
    ) -> None:
        """
        Set unit color temperature
        """
        await self.units[network_id].set_unit_rgb(
            unit_id=unit_id, color_value=color_value, send_rgb_format=send_rgb_format
        )

    async def set_unit_color_temperature(
        self, *, unit_id: int, network_id: str, value: int, source: str = "TW"
    ) -> None:
        """
        Set unit color temperature
        """
        await self.units[network_id].set_unit_color_temperature(
            unit_id=unit_id, value=value, source=source
        )

    async def request(
        self, method, json=None, url=None, headers=None, **kwargs
    ) -> dict:
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

        except client_exceptions.ClientError as err:
            raise err
