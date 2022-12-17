"""Casambi implementation."""

import logging
import time
import random
import re

from typing import Tuple
from pprint import pformat
from asyncio import TimeoutError, sleep
from aiohttp import client_exceptions

from .errors import (
    AiocasambiException,
    Unauthorized,
    RequestedDataNotFound,
    QoutaLimitsExceeded,
    ERROR_CODES,
    get_error,
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
    MAX_RETRIES,
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

    def get_units(self) -> list:
        """Getter for getting units."""
        result = []
        for network_id in self._network_ids:
            for unit in self.units[network_id].get_units():
                result.append(unit)

        return result

    def get_scenes(self) -> list:
        """Getter for getting scenes."""
        result = []
        for network_id in self._network_ids:
            for scene in self.scenes[network_id].get_scenes():
                result.append(scene)

        return result

    async def create_session(self) -> None:
        """
        Create session
        """
        LOGGER.debug("Create session called!")

        for i in range(0, MAX_RETRIES):
            try:
                if self.user_password:
                    LOGGER.debug("Creating user session")

                    await self.create_user_session()

                    return
            except TimeoutError:
                dbg_msg = "caught asyncio.TimeoutError when "
                dbg_msg += "trying to create user session"
                dbg_msg += f",  trying again, try: {i}"
                LOGGER.debug(dbg_msg)

                await sleep(self.network_timeout)

                continue

            try:
                if self.network_password:
                    LOGGER.debug("Creating network session")

                    await self.create_network_session()

                    return
            except TimeoutError:
                dbg_msg = "caught TimeoutError when trying to "
                dbg_msg += "create network session, trying again"
                LOGGER.debug(dbg_msg)

                await sleep(self.network_timeout)

                continue

        err_msg = "create_session failed to setup session!"

        LOGGER.error(err_msg)

        raise AiocasambiException(err_msg)

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

        LOGGER.debug("create_user_session called")

        headers = {"Content-type": "application/json", "X-Casambi-Key": self.api_key}

        auth = {
            "email": self.email,
            "password": self.user_password,
        }

        dbg_msg = f"create_user_session headers: {pformat(headers)} "
        dbg_msg += f"auth: {pformat(auth)}"
        LOGGER.debug(dbg_msg)

        data = None
        try:
            data = await self.request("post", url=url, json=auth, headers=headers)
        except Unauthorized as err:
            LOGGER.error("create_user_session caught Unauthorized exception")
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

        dbg_msg = f"network_ids: {pformat(self._network_ids)} "
        dbg_msg += f"session_ids: {pformat(self._session_ids)}"
        LOGGER.debug(dbg_msg)

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
        LOGGER.debug("create_network_session called")

        url = f"{self.rest_url}/networks/session"

        headers = {"Content-type": "application/json", "X-Casambi-Key": self.api_key}

        auth = {
            "email": self.email,
            "password": self.network_password,
        }

        dbg_msg = f"create_network_session headers: {headers} auth: {auth}"
        LOGGER.debug(dbg_msg)

        data = None
        try:
            data = await self.request("post", url=url, json=auth, headers=headers)
        except Unauthorized as err:
            err_msg = "create_network_session: caught Unauthorized exception"
            LOGGER.error(err_msg)
            raise err

        dbg_msg = f"create_network_session: data from request {pformat(data)}"
        LOGGER.debug(dbg_msg)

        for network_id in data.keys():
            self._network_ids.add(data[network_id]["id"])
            self._session_ids[network_id] = data[network_id]["sessionId"]

        dbg_msg = f"create_network_session: network_ids: {pformat(self._network_ids)} "
        dbg_msg += f"session_ids: {pformat(self._session_ids)}"
        LOGGER.debug(dbg_msg)

    async def get_network_information(self) -> dict:
        """Get network information."""
        # GET https://door.casambi.com/v1/networks/{id}
        result = {}
        failed_network_ids = []

        LOGGER.debug("get_network_information called")

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
            except Unauthorized:
                err_msg = "get_network_information caught Unauthorized"
                err_msg += f" exception for network_id: {network_id}"
                LOGGER.error(err_msg)

                failed_network_ids.append(network_id)

                continue

            dbg_msg = f"get_network_information response: {pformat(data)}"
            LOGGER.debug(dbg_msg)

            result[network_id] = data

        if len(result) == 0:
            err_msg = "get_network_information failed "
            err_msg += "to get any network information!"
            raise AiocasambiException(err_msg)

        for failed_network_id in failed_network_ids:
            self.__remove_network_id(network_id=failed_network_id)

        return result

    async def get_network_state(self) -> dict:
        """Get network state.

        GET https://door.casambi.com/v1/networks/{networkId}/state
        {
            "id": "VcrTwqLZJ26UYMXxTClmpfZxELcrPUAa",
            "name": "Demo Room",
            "revision": 125,
            "grade": "EVOLUTION",
            "address": "b02ef7956bcc",
            "gateway": {
                "name": "Demo iPad"
            },
            "type": "OPEN",
            "timezone": "Europe/Helsinki",
            "dimLevel": 0.5,
            "activeScenes": [
                3,
                4
            ],
            "photos": [
                {
                    "name": "Photo",
                    "controls": [],
                    "image": "iR4aIP3vXcB348Pijif2d4Y7AnowFbdD",
                    "position": 0
                },
                {
                    "name": "Photo",
                    "controls": [],
                    "image": "KLejfitLiEFeiUnhak6ID69VzJhvWYER",
                    "position": 1
                }
            ],
            "units": {
                "15": {
                    "id": 15,
                    "address": "44363c069a45",
                    "name": "Sensor Z",
                    "position": 4,
                    "fixtureId": 45602,
                    "firmwareVersion": "32.10",
                    "groupId": 0,
                    "priority": 0,
                    "scene": 0,
                    "online": false,
                    "condition": 0,
                    "status": "ok",
                    "activeSceneId": 0,
                    "controls": [
                        [
                            {
                                "type": "Presence",
                                "status": "absent"
                            },
                            {
                                "level": 0,
                                "type": "Lux",
                                "value": 0
                            },
                            {
                                "type": "Switch"
                            }
                        ]
                    ],
                    "details": {
                        "_name": "ccb3e63c069a",
                        "OEM": "Tridonic GmbH & Co KG",
                        "fixture_model": "bDW (PIR)"
                    },
                    "dimLevel": 0,
                    "type": "Sensor"
                },
                "18": {
                    "id": 18,
                    "address": "dfe579c30c88",
                    "name": "TestUnit",
                    "image": "456ghkOxsfuE6GTR6utJl8OEAPkSqh",
                    "position": 4,
                    "fixtureId": 16574,
                    "firmwareVersion": "32.10",
                    "groupId": 0,
                    "priority": 3,
                    "scene": 0,
                    "online": true,
                    "condition": 134,
                    "status": "status_message",
                    "activeSceneId": 4,
                    "controls": [
                        [
                            {
                                "type": "Dimmer",
                                "value": 1
                            },
                            {
                                "source": "XY",
                                "type": "Colorsource"
                            },
                            {
                                "x": 0.14753297508549096,
                                "y": 0.13727405959941377,
                                "rgb": "rgb(136, 255, 255)",
                                "type": "Color"
                            },
                            {
                                "tw": 23.52941,
                                "min": 2700,
                                "max": 6000,
                                "type": "CCT",
                                "value": 6000,
                                "level": 1
                            }
                        ]
                    ],
                    "dimLevel": 1,
                    "type": "Luminaire"
                }
            },
            "scenes": {
                "1": {
                    "name": "Timer",
                    "id": 1,
                    "position": 0,
                    "icon": 0,
                    "color": "#FFFFFF",
                    "type": "REGULAR",
                    "hidden": false,
                    "units": {
                        "12": {
                            "id": 12
                        }
                    }
                },
                "4": {
                    "name": "Presence",
                    "id": 2,
                    "position": 1,
                    "icon": 0,
                    "color": "#06FF29",
                    "type": "REGULAR",
                    "hidden": false,
                    "units": {
                        "18": {
                            "id": 18
                        }
                    }
                }
            },
            "groups": {
                "3": {
                    "id": 3,
                    "name": "Demo Group",
                    "position": 2,
                    "units": [
                        {
                            "0": 12,
                            "position": 0
                        }
                    ]
                }
            }
        }
        """
        result = []
        failed_network_ids = []

        if not self._network_ids or len(self._network_ids) == 0:
            raise AiocasambiException("Network ids not set")

        dbg_msg = f"get_network_state called units: {pformat(self.units)}"
        LOGGER.debug(dbg_msg)

        for network_id in self._network_ids:
            failed_network_request = False
            self.set_session_id(session_id=self._session_ids[network_id])
            url = f"{self.rest_url}/networks/{network_id}/state"

            dbg_msg = f"get_network_state request url: {url} headers= {self.headers}"
            LOGGER.debug(dbg_msg)

            data = None

            for i in range(0, MAX_RETRIES):
                try:
                    data = await self.request("get", url=url, headers=self.headers)
                except Unauthorized:
                    err_msg = "get_network_state caught Unauthorized "
                    err_msg += f"exception for network_id: {network_id}"
                    LOGGER.error(err_msg)

                    failed_network_ids.append(network_id)
                    failed_network_request = True

                    break
                except TimeoutError:
                    dbg_msg = "caught asyncio.TimeoutError when initialize "
                    dbg_msg += "tried  to fetch network information, "
                    dbg_msg += f"trying again, try {i}"
                    LOGGER.debug(dbg_msg)

                    await sleep(self.network_timeout)

                    continue

                # Success!
                break

            if failed_network_request:
                continue

            if not data:
                error_msg = "get_network_state failed to get network state!"
                LOGGER.error(error_msg)

                raise AiocasambiException(error_msg)

            dbg_msg = "get_network_state response: {data}"
            LOGGER.debug(dbg_msg)

            self.units[network_id].process_network_state(data)

            self.callback(
                SIGNAL_UNIT_PULL_UPDATE, self.units[network_id].get_units_unique_ids()
            )

            result.append(data)

        if len(result) == 0:
            raise AiocasambiException("get_network_state failed to get any state!")

        for failed_network_id in failed_network_ids:
            self.__remove_network_id(network_id=failed_network_id)

        return result

    async def init_unit_state_controls(self, *, network_id: str) -> None:
        """
        Getter for getting the unit state from Casambis cloud api
        """
        # GET https://door.casambi.com/v1/networks/{id}
        unit_mac_regexp = re.compile(
            r"(?P<network_id>[a-zA-Z0-9]+)-(?P<mac_address>[0-9a-f]{12})$"
        )
        unit_id_regexp = re.compile(r"(?P<network_id>[a-zA-Z0-9]+)-(?P<unit_id>\d+)$")
        unique_ids = self.units[network_id].get_units_unique_ids()

        dbg_msg = f"init_unit_state_controls unique_ids: {pformat(unique_ids)}"
        LOGGER.debug(dbg_msg)

        for unique_unit_id in unique_ids:
            network_id = None
            mac_address = None
            unit_id = None
            match = unit_mac_regexp.match(unique_unit_id)

            if match:
                network_id = match.group("network_id")
                mac_address = match.group("mac_address")

                unit_id = self.units[network_id].get_unit_id_from_mac_address(
                    mac_address=mac_address
                )
            else:
                match = unit_id_regexp.match(unique_unit_id)
                network_id = match.group("network_id")
                unit_id = match.group("unit_id")

            data = None

            dbg_msg = f"init_unit_state_controls unique_unit_id: {unique_unit_id} "
            dbg_msg += f"unit_id: {unit_id}"
            LOGGER.debug(dbg_msg)

            for i in range(0, MAX_RETRIES):
                try:
                    data = await self.get_unit_state_controls(
                        unit_id=unit_id, network_id=network_id
                    )
                except TimeoutError:
                    dbg_msg = "caught asyncio.TimeoutError when initialize tried "
                    dbg_msg += f"to fetch network information, trying again, try: {i}"
                    LOGGER.debug(dbg_msg)

                    await sleep(self.network_timeout)

                    continue

                # Success!
                break

            if not data:
                dbg_msg = "init_unit_state_controls failed to get unit state "
                dbg_msg += f"for unit: {unique_unit_id} data: {pformat(data)}"

                LOGGER.debug(dbg_msg)

                return

            self.units[network_id].set_controls(unit_id=unit_id, data=data)

    def get_unit(self, *, unit_id: int, network_id: str) -> Unit:
        """
        Get specific unit
        """
        return self.units[network_id].get_unit(unit_id=unit_id)

    def get_unit_value(self, *, unit_id: int, network_id: str) -> int:
        """
        Get the unit value
        """
        return self.units[network_id].get_unit_value(unit_id=unit_id)

    def get_unit_distribution(self, *, unit_id: int, network_id: str) -> int:
        """
        Get the unit distribution
        """
        return self.units[network_id].get_unit_distribution(unit_id=unit_id)

    async def get_unit_state(self, *, unit_id: int, network_id: str) -> dict:
        """
        Getter for getting the unit state from Casambis cloud api
        """
        # GET https://door.casambi.com/v1/networks/{id}

        if not self._network_ids or len(self._network_ids) == 0:
            raise AiocasambiException("Network ids not set")

        session_id = self._session_ids[network_id]

        self.set_session_id(session_id=session_id)

        url = "https://door.casambi.com/v1/networks/"
        url += f"{network_id}/units/{unit_id}/state"

        data = None
        try:
            data = await self.request("get", url=url, headers=self.headers)
        except Unauthorized as err:
            err_msg = "get_unit_state caught Unauthorized exception, "
            err_msg += f"unit_id: {unit_id}, network_id: {network_id}"
            LOGGER.error(err_msg)

            raise err
        except AiocasambiException as err:
            err_msg = "get_unit_state caught AiocasambiException exception, "
            err_msg += f"unit_id: {unit_id}, network_id: {network_id} "
            err_msg += f"err: {err}"
            LOGGER.exception(err_msg)

            raise err

        dbg_msg = f"get_unit_state called, unit_id: {unit_id}, "
        dbg_msg += f"network_id: {network_id} session_id: {session_id} "
        dbg_msg += f"data: {pformat(data)}"

        LOGGER.debug(dbg_msg)

        return data

    async def get_fixture_information(
        self, *, network_id: str, fixture_id: int
    ) -> dict:
        """
        Get fixure information

        GET https://door.casambi.com/v1/fixtures/{id}

        {
            "id": 23456,
            "type": "Driver",
            "vendor": "Oktalite Lichttechnik GmbH",
            "model": "Oktalite AGIRA PLUS",
            "translations": {},
            "controls": [
                {
                    "type": "button",
                    "name": "Button",
                    "buttonLabel": "Button",
                    "dataname": "button",
                    "id": 0,
                    "readonly": true
                },
                {
                    "type": "dimmer",
                    "id": 1,
                    "readonly": false
                },
                {
                    "type": "rgb",
                    "id": 7,
                    "readonly": false
                },
                {
                    "type": "temperature",
                    "id": 25,
                    "readonly": false
                },
                {
                    "type": "colorsource",
                    "id": 31,
                    "readonly": false
                },
                {
                    "type": "slider",
                    "name": "Slider",
                    "unit": "",
                    "id": 33,
                    "readonly": false,
                    "valueType": "FLOAT"
                }
            ]
        }
        """
        if fixture_id == 0:
            LOGGER.debug("get_fixture_information fixture_id is 0 exiting")
            return {}

        self.set_session_id(session_id=self._session_ids[network_id])
        url = f"{self.rest_url}/fixtures/{fixture_id}"

        dbg_msg = f"get_fixture_information request <url: {url} "
        dbg_msg += f"headers= {self.headers}>"
        LOGGER.debug(dbg_msg)

        data = None
        try:
            data = await self.request("get", url=url, headers=self.headers)
        except RequestedDataNotFound:
            warn_msg = f"Failed to get fixture information for {fixture_id}"
            LOGGER.warning(warn_msg)
            return {}
        except Unauthorized:
            warn_msg = f"get_fixture_information caught Unauthorized "
            warn_msg += f"exception for network_id: {network_id}"
            LOGGER.warning(warn_msg)

            # Hue lights don't support get_fixture_information,
            # thats why its no raise of exception
            return {}

        dbg_msg = f"get_fixture_information response: {pformat(data)}"
        LOGGER.debug(dbg_msg)

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
        dbg_msg = (
            f"get_unit_state_controls called unit_id:{unit_id} network_id: {network_id}"
        )
        LOGGER.debug(dbg_msg)

        data = await self.get_unit_state(unit_id=unit_id, network_id=network_id)

        dbg_msg = f"get_unit_state_controls data: {pformat(data)}"
        LOGGER.debug(dbg_msg)

        if "controls" in data:
            return data["controls"]

        return []

    async def initialize(self) -> None:
        """Initialiser"""

        LOGGER.debug("initialize called")

        network_information = None

        for _ in range(0, MAX_RETRIES):
            try:
                network_information = await self.get_network_information()
                break
            except TimeoutError:
                dbg_msg = "caught asyncio.TimeoutError when initialize "
                dbg_msg += "tried to fetch network information, trying again"
                LOGGER.debug(dbg_msg)

                await sleep(self.network_timeout)

                continue

            # Success!
            break

        if not network_information:
            error_msg = "initialize failed to fetch network information"

            LOGGER.error(error_msg)

            raise AiocasambiException(error_msg)

        for network_id, data in network_information.items():
            self.units[network_id] = Units(
                data["units"],
                controller=self,
                network_id=network_id,
                wire_id=0,
            )

            self.scenes[network_id] = Scenes(
                data["scenes"],
                controller=self,
                network_id=network_id,
                wire_id=0,
            )

        dbg_msg = "initialize network__information: "
        dbg_msg += f"{pformat(network_information)}"
        LOGGER.debug(dbg_msg)

        # Get initial network state
        await self.get_network_state()

        dbg_msg = "initialize getting unit state for all units in "
        dbg_msg += f"network_ids: {pformat(self._network_ids)}"
        LOGGER.debug(dbg_msg)

        for network_id in self._network_ids:
            await self.init_unit_state_controls(network_id=network_id)

        # Get fixture information
        for network_id in self._network_ids:
            await self.units[network_id].get_fixture_information_for_all_units()

        return

    async def start_websockets(self) -> None:
        """
        Start websocket for all networks
        """
        LOGGER.debug("start_websockets called")

        for network_id in self._network_ids:
            dbg_msg = f"start_websockets starting network_id: {network_id}"
            LOGGER.debug(dbg_msg)

            await self.start_websocket(network_id=network_id)

    async def start_websocket(self, *, network_id: str) -> None:
        """
        Start websession and websocket to Casambi.
        """
        dbg_msg = f"start_websocket called network_id: {network_id}"
        LOGGER.debug(dbg_msg)

        wire_id = random.randint(1, MAX_NETWORK_IDS)

        while wire_id not in self._wire_id_to_network_id:
            wire_id = random.randint(1, MAX_NETWORK_IDS)
            self._wire_id_to_network_id[wire_id] = network_id

        dbg_msg = (
            f"start_websocket generate wire_id: {wire_id} network_id: {network_id}"
        )
        LOGGER.debug(dbg_msg)

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
            network_timeout=self.network_timeout,
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
            msg += f"last websocket ping: {self._last_websocket_ping} "
            msg += f"websocket states: {self.get_websockets_states()} "
            LOGGER.debug(msg)
            return

        for wire_id, network_id in self._wire_id_to_network_id.items():
            message = {
                "method": "ping",
                "wire": wire_id,
            }

            dbg_msg = f"Sending websocket ping: {message}"
            LOGGER.debug(dbg_msg)

            succcess = await self.websocket[network_id].send_message(message)

            if not succcess:
                # Try to reconnect
                await self.reconnect()

        self._last_websocket_ping = current_time

    async def ws_send_message(self, msg: dict, network_id: str) -> None:
        """Send websocket message to casambi api"""
        await self.ws_ping()

        dbg_msg = f"Sending websocket message: msg {msg}"
        LOGGER.debug(dbg_msg)

        succcess = await self.websocket[network_id].send_message(msg)

        if not succcess:
            # Try to reconnect
            await self.reconnect()

    def get_websockets(self) -> list:
        """
        Get websockets
        """
        result = []

        for _, item in self.websocket.items():
            result.append(item)

        return result

    def get_websockets_states(self) -> str:
        """
        Getter for websocket state
        """
        result = []
        for network_id, _ in self.websocket.items():
            result.append(self.websocket[network_id].state)

        return result

    def get_websocket_state(self, *, network_id: str) -> str:
        """
        Get websocket state
        """
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

    def session_handler(self, signal: str, wire_id: str) -> None:
        """Signalling from websocket.

        data - new data available for processing.
        state - network state has changed.
        """
        if len(self.websocket) == 0:
            return

        dbg_msg = f"session_handler: websockets {self.websocket}"
        LOGGER.debug(dbg_msg)

        if signal == SIGNAL_DATA:
            LOGGER.debug(f"session_handler is handling SIGNAL_DATA: {signal}")

            network_id = self._wire_id_to_network_id[wire_id]

            new_items = self.message_handler(self.websocket[network_id].data, wire_id)

            if new_items and self.callback:
                self.callback(SIGNAL_DATA, new_items)
        elif signal == SIGNAL_CONNECTION_STATE and self.callback:
            dbg_msg = "session_handler is handling "
            dbg_msg += f"SIGNAL_CONNECTION_STATE: {signal}"
            LOGGER.debug(dbg_msg)

            network_id = self._wire_id_to_network_id[wire_id]

            self.callback(SIGNAL_CONNECTION_STATE, self.websocket[network_id].state)
        else:
            dbg_msg = f"session_handler is NOT handling signal: {signal}"
            LOGGER.debug(dbg_msg)

    def message_handler(self, message: dict, wire_id: str) -> dict:
        """
        Receive event from websocket and identifies where the event belong.
        """
        changes = {}

        dbg_msg = f"message_handler recieved websocket message: {message}"
        LOGGER.debug(dbg_msg)

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
        all_running = True

        states = self.get_websockets_states()
        for state in states:
            if state != STATE_RUNNING:
                all_running = False

        if all_running:
            return

        # Try to reconnect
        await self.reconnect()

    async def reconnect(self) -> None:
        """
        async function for reconnecting.
        """
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
            except QoutaLimitsExceeded as err:
                dbg_msg = f"caught QoutaLimitsExceeded exception: {err}, trying again"
                LOGGER.debug(dbg_msg)

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
                LOGGER.debug(
                    "caught asyncio.TimeoutError during reconnection, trying again"
                )

                await sleep(self.network_timeout)

                continue

            # Reconnected
            self._reconnecting = False
            break

        # Set new session ids for websocket
        for network_id, _ in self.websocket.items():
            self.websocket[network_id].session_id = self._session_ids[network_id]

        connected = True
        for state in self.get_websockets_states():
            if state != STATE_RUNNING:
                connected = False
        if connected:
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
        """
        Setter for wire_id
        """
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

    async def __remove_network_id(self, *, network_id: str) -> None:
        """
        Private function for removing network_id
        """
        wire_ids_to_remove = []
        if network_id in self.websocket:
            # Stopping websocket
            await self.stop_websocket(network_id=network_id)
            self.websocket.pop(network_id)

        if network_id in self._network_ids:
            self._network_ids.pop(network_id)

        if network_id in self._session_ids:
            self._session_ids.pop(network_id)

        for wire_id, wire_network_id in self._wire_id_to_network_id.items():
            if wire_network_id == network_id:
                wire_ids_to_remove.append(wire_id)

        for wire_id in wire_ids_to_remove:
            self._wire_id_to_network_id.pop(wire_id)

        if network_id in self.units:
            self.units.pop(network_id)

        if network_id in self.scenes:
            self.scenes.pop(network_id)

    async def request(
        self, method, json=None, url=None, headers=None, **kwargs
    ) -> dict:
        """Make a request to the API."""
        await self.ws_ping()

        dbg_msg = f"request url: {url}"
        LOGGER.debug(dbg_msg)

        try:
            async with self.session.request(
                method,
                url,
                json=json,
                ssl=self.sslcontext,
                headers=headers,
                **kwargs,
            ) as res:
                dbg_msg = f"request status:{res.status} "
                dbg_msg += f"content_type:{res.content_type} "
                dbg_msg += f"result:{res}"
                LOGGER.debug(dbg_msg)

                if res.status in ERROR_CODES:
                    text = await res.text()
                    error = get_error(status_code=res.status)

                    err_msg = f"got status_code: {res.status} text: {text}"
                    LOGGER.error(err_msg)

                    raise error(err_msg)

                if res.content_type == "application/json":
                    response = await res.json()

                    return response
                return res

        except client_exceptions.ClientError as err:
            raise err
