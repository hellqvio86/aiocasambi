"""State representation of Casanbi Unit"""

import logging

from typing import Tuple, Union
from pprint import pformat
from .unit import Unit

LOGGER = logging.getLogger(__name__)


class Units:
    """
    Class for representing Casambi Units
    """

    def __init__(
        self, units: set, *, network_id, wire_id, controller, online=True
    ) -> None:
        self._network_id = network_id
        self._wire_id = wire_id
        self._controller = controller
        self.units = {}
        self._online = online

        self.__process_units(units)

    def handle_peer_changed(self, message: dict) -> dict:
        """
        Function for handling peer change
        """
        changes = {}
        if "online" in message:
            self.online = message["online"]

        for key, unit in self.units.items():
            changes[key] = unit

        return changes

    def process_network_state(self, data: dict) -> None:
        """
         'dimLevel': 1.0 is unit "ON"

        Event like:

        {'activeScenes': [],
        'dimLevel': 0.41263616557734206,
        'gateway': {'name': 'Galaxy S8'},
        'grade': 'CLASSIC',
        'groups': {},
        'id': '...',
        'mac': 'ffffffffffff',
        'name': 'Foobar',
        'photos': [],
        'revision': 97,
        'scenes': {'1': {'color': '#FFFFFF',
                        'hidden': False,
                        'icon': 0,
                        'id': 1,
                        'name': 'Foo',
                        'position': 0,
                        'type': 'REGULAR',
                        'units': {'10': {'id': 10}, '8': {'id': 8}}},
                    },
        'timezone': 'Europe/Stockholm',
        'type': 'PROTECTED',
        'units': {'1': {'activeSceneId': 0,
                        'address': 'ffffffffffff',
                        'condition': 0,
                        'controls': [[{'status': 'ok', 'type': 'Overheat'},
                                    {'type': 'Dimmer',
                                        'value': 0.7372549019607844}]],
                        'dimLevel': 0.7372549019607844,
                        'fixtureId': 859,
                        'groupId': 0,
                        'id': 1,
                        'image': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                        'name': 'Spottar bad',
                        'on': True,
                        'online': True,
                        'position': 0,
                        'priority': 3,
                        'status': 'ok',
                        'type': 'Luminaire'},
                '10': {'activeSceneId': 0,
                        'address': 'ffffffffffff',
                        'condition': 0,
                        'controls': [[{'status': 'ok', 'type': 'Overheat'},
                                        {'type': 'Dimmer', 'value': 1.0}]],
                        'dimLevel': 1.0,
                        'fixtureId': 2516,
                        'groupId': 0,
                        'id': 10,
                        'image': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                        'name': 'Skärmtak',
                        'on': True,
                        'online': True,
                        'position': 7,
                        'priority': 3,
                        'status': 'ok',
                        'type': 'Luminaire'},
                '12': {'activeSceneId': 0,
                        'address': 'ffffffffffff',
                        'condition': 0,
                        'controls': [[{'status': 'ok', 'type': 'Overheat'},
                                        {'type': 'Dimmer',
                                        'value': 0.9764705882352941}]],
                        'dimLevel': 0.9764705882352941,
                        'fixtureId': 2516,
                        'groupId': 0,
                        'id': 12,
                        'image': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                        'name': 'Husnummer',
                        'on': True,
                        'online': True,
                        'position': 10,
                        'priority': 3,
                        'status': 'ok',
                        'type': 'Luminaire'},
                '2': {'activeSceneId': 0,
                        'address': 'ffffffffffff',
                        'condition': 0,
                        'controls': [[{'status': 'ok', 'type': 'Overheat'},
                                    {'type': 'Dimmer', 'value': 0.0}]],
                        'dimLevel': 0.0,
                        'fixtureId': 859,
                        'groupId': 0,
                        'id': 2,
                        'image': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                        'name': 'Tvättstuga bänk',
                        'on': True,
                        'online': True,
                        'position': 1,
                        'priority': 0,
                        'status': 'ok',
                        'type': 'Luminaire'},
               }
        """
        try:
            if "units" not in data:
                # Safe guard
                LOGGER.debug(
                    f"process_network_state - units not in data: {pformat(data)}"
                )
                return
        except TypeError as err:
            LOGGER.error(f"process_network_state - unknown data: {pformat(data)}")
            raise err

        LOGGER.debug(f"process_network_state - data={pformat(data)}")

        for unit_key in data["units"]:
            unit_data = data["units"][unit_key]
            key = f"{self._network_id}-{unit_key}"

            self.units[key].online = unit_data["online"]
            self.units[key].name = unit_data["name"]
            if unit_data["online"]:
                # self.units[key].value = unit_data['dimLevel']
                self.units[key].controls = unit_data["controls"]

    def process_unit_event(self, msg: dict) -> dict:
        """
        Event like:
        {
        'activeSceneId': 0,
        'condition': 0.0,
        'controls': [{'status': 'ok', 'type': 'Overheat'},
                    {'type': 'Dimmer', 'value': 0.0}],
        'details': {'OEM': 'Vadsbo',
                    '_name': 'ffffffffffff',
                    'address': 'ffffffffffff',
                    'fixture': 2516.0,
                    'fixture_model': 'LD220WCM_onoff',
                    'name': 'Fooobar'},
        'id': 12,
        'method': 'unitChanged',
        'on': True,
        'online': True,
        'sensors': [],
        'status': 'ok',
        'wire': 3
        }

        Unit off:
        {'activeSceneId': 0,
        'condition': 0.0,
        'controls': [{'status': 'ok', 'type': 'Overheat'},
                    {'type': 'Dimmer', 'value': 0.0}],
        'details': {'OEM': 'Vadsbo',
                    '_name': 'ffffffffffff',
                    'address': 'ffffffffffff',
                    'fixture': 859.0,
                    'fixture_model': 'LD220WCM',
                    'name': 'Foo'},
        'id': 2,
        'method': 'unitChanged',
        'on': True,
        'online': True,
        'priority': 3.0,
        'sensors': [],
        'status': 'ok',
        'wire': 3}


        Unit on:
        {'activeSceneId': 0,
        'condition': 0.0,
        'controls': [{'status': 'ok', 'type': 'Overheat'},
                    {'type': 'Dimmer', 'value': 1.0}],
        'details': {'OEM': 'Vadsbo',
                    '_name': 'ffffffffffff',
                    'address': 'ffffffffffff',
                    'fixture': 859.0,
                    'fixture_model': 'LD220WCM',
                    'name': 'Foo'},
        'id': 2,
        'method': 'unitChanged',
        'on': True,
        'online': True,
        'priority': 3.0,
        'sensors': [],
        'status': 'ok',
        'wire': 3}

        Need to handle:
        {
            'unit': 1.0,
            'condition': 0.0,
            'wire': 9,
            'method': 'unitChanged',
            'online': True,
            'state': 'fc03',
            'priority': 3.0,
            'scene': 0.0,
            'on': True
        }
        """
        changes = {}

        LOGGER.debug(f"process_unit_event - Processing msg: {pformat(msg)}")

        if "id" not in msg:
            error_msg = "processing_unit_event - discarding message, "
            error_msg += f"id is missing in msg: {pformat(msg)}"

            LOGGER.error(error_msg)

            return None

        key = f"{self._network_id}-{msg['id']}"

        if "online" in msg and not msg["online"]:
            LOGGER.debug(
                f"processing_unit_event - Gateway is not online msg: {pformat(msg)}"
            )

        if "method" in msg and msg["method"] == "unitChanged":
            controls = msg["controls"]
            for control in controls:

                LOGGER.debug(
                    f'processing_unit_event - method "unitChanged" control: {pformat(control)}'
                )

                if "type" in control and control["type"] == "Dimmer":
                    name = ""
                    if "details" in msg and "name" in msg["details"]:
                        name = (msg["details"]["name"]).strip()
                    elif "name" in msg:
                        name = (msg["name"]).strip()

                    dbg_msg = (
                        f"processing_unit_event - key: {key} name: {name} msg: {msg} "
                    )
                    dbg_msg += "method unit changed control"
                    dbg_msg += f" value: {pformat(control['value'])}"
                    LOGGER.debug(dbg_msg)

                    if key not in self.units:
                        # New unit discovered
                        address = None
                        if "details" in msg and "address" in msg["details"]:
                            address = msg["details"]["address"]
                        elif "address" in msg:
                            address = msg["address"]
                        online = False
                        type = None
                        if "details" in msg and "type" in msg["details"]:
                            type = msg["details"]["type"]
                        elif "type" in msg:
                            type = msg["type"]
                        unit_id = msg["id"]
                        controls = []

                        if "online" in msg:
                            online = msg["online"]

                        if "controls" in msg:
                            controls = msg["controls"]

                        unit = Unit(
                            name=name,
                            address=address,
                            type=type,
                            unit_id=unit_id,
                            online=online,
                            wire_id=self._wire_id,
                            network_id=self._network_id,
                            controller=self._controller,
                            controls=controls,
                        )

                        self.units[key] = unit

                    # Update value
                    self.units[key].value = control["value"]

                    if "details" in msg and "fixture" in msg["details"]:
                        self.units[key].fixture = msg["details"]["fixture"]
                    elif "fixture" in msg:
                        self.units[key].fixture = msg["fixture"]

                    if "online" in msg:
                        self.units[key].online = msg["online"]

                    if "details" in msg and "fixture_model" in msg["details"]:
                        self.units[key].fixture_model = msg["details"]["fixture_model"]
                    elif "fixture_model" in msg:
                        self.units[key].fixture_model = msg["fixture_model"]

                    if "details" in msg and "OEM" in msg["details"]:
                        self.units[key].oem = msg["details"]["OEM"]
                    elif "OEM" in msg:
                        self.units[key].oem = msg["OEM"]

                    if "details" in msg and "controls" in msg["details"]:
                        self.units[key].controls = msg["details"]["controls"]
                    elif "controls" in msg:
                        self.units[key].controls = msg["controls"]

                    changes[key] = self.units[key]

                if "type" in control and control["type"] == "Vertical":
                    dbg_msg = (
                        f"processing_unit_event - key: {key} name: {name} msg: {msg} "
                    )
                    dbg_msg += "method unit changed control"
                    dbg_msg += f" distribution: {pformat(control['value'])}"
                    LOGGER.debug(dbg_msg)

                    # Update distribution
                    self.units[key].distribution = control["value"]

        return changes

    @property
    def online(self) -> bool:
        """
        Getter for online
        """
        return self._online

    @online.setter
    def online(self, online: bool) -> None:
        """
        Setter for online
        """
        self._online = online

        for _, unit in self.units.items():
            unit.online = online

    def get_unit(self, *, unit_id: int) -> Unit:
        """
        Get unit
        """
        key = f"{self._network_id}-{unit_id}"

        return self.units[key]

    def get_unit_value(self, *, unit_id: int) -> int:
        """
        Get unit
        """
        key = f"{self._network_id}-{unit_id}"

        return self.units[key].value

    def get_unit_distribution(self, *, unit_id: int) -> int:
        """
        Get unit distribution
        """
        key = f"{self._network_id}-{unit_id}"

        return self.units[key].distribution

    def get_units(self) -> list:
        """
        Getter for all units
        """
        result = []
        for _, value in self.units.items():
            result.append(value)

        return result

    def get_units_unique_ids(self) -> list:
        """
        Getter for getting all units uniq ids
        """
        result = []
        for _, value in self.units.items():
            result.append(value.unique_id)

        return result

    async def turn_unit_on(self, *, unit_id: int) -> None:
        """
        Turn unit on
        """
        key = f"{self._network_id}-{unit_id}"

        await self.units[key].turn_unit_on()

    async def turn_unit_off(self, *, unit_id: int) -> None:
        """
        Turn unit off
        """
        key = f"{self._network_id}-{unit_id}"

        await self.units[key].turn_unit_off()

    def set_wire_id(self, *, wire_id: int) -> None:
        """
        Setter for wire id
        """
        self._wire_id = wire_id

        for _, unit in self.units.items():
            unit.set_wire_id(wire_id=wire_id)

    def set_controls(self, *, unit_id: int, data: Union[list, dict]) -> None:
        """
        Setter for unit state
        """
        key = f"{self._network_id}-{unit_id}"

        self.units[key].controls = data

    def supports_rgbw(self, *, unit_id: int) -> bool:
        """
        Check if unit supports RGB
        """
        key = f"{self._network_id}-{unit_id}"
        result = self.units[key].supports_rgbw()

        return result

    def supports_rgb(self, *, unit_id: int) -> bool:
        """
        Check if unit supports RGB
        """
        key = f"{self._network_id}-{unit_id}"
        result = self.units[key].supports_rgb()

        return result

    def supports_color_temperature(self, *, unit_id: int) -> bool:
        """
        Check if unit supports color temperature
        """
        key = f"{self._network_id}-{unit_id}"
        result = self.units[key].supports_color_temperature()

        return result

    def supports_brightness(self, *, unit_id: int) -> bool:
        """
        Check if unit supports brightness temperature
        """
        key = f"{self._network_id}-{unit_id}"
        result = self.units[key].supports_brightness()

        return result

    def supports_distribution(self, *, unit_id: int) -> bool:
        """
        Check if unit supports distribution
        """
        key = f"{self._network_id}-{unit_id}"
        result = self.units[key].supports_distribution()

        return result

    def get_supported_color_temperature(self, *, unit_id: int) -> Tuple[int, int, int]:
        """
        Get supported color temperatures
        """
        key = f"{self._network_id}-{unit_id}"
        (cct_min, cct_max, current) = self.units[key].get_supported_color_temperature()

        return (cct_min, cct_max, current)

    async def set_unit_rgbw(
        self, *, unit_id: int, color_value: Tuple[int, int, int, int]
    ) -> None:
        """
        Set unit rgb
        """
        key = f"{self._network_id}-{unit_id}"
        await self.units[key].set_unit_rgbw(color_value=color_value)

    async def set_unit_rgb(
        self, *, unit_id: int, color_value: Tuple[int, int, int], send_rgb_format=False
    ) -> None:
        """
        Set unit rgbw
        """
        key = f"{self._network_id}-{unit_id}"
        await self.units[key].set_unit_rgb(
            color_value=color_value, send_rgb_format=send_rgb_format
        )

    async def set_unit_color_temperature(
        self, *, unit_id: int, value: int, source="TW"
    ) -> None:
        """
        Set unit color temperature
        """
        key = f"{self._network_id}-{unit_id}"
        await self.units[key].set_unit_color_temperature(value=value, source=source)

    def __process_units(self, units: list):
        """
        Function for processing units
        Units raw format:
        {'1': {
                'address': 'ffffffffffff',
                'fixtureId': 859,
                'groupId': 0,
                'id': 1,
                'image': 'FFFFFFFFF',
                'name': 'Foo',
                'position': 0,
                'type': 'Luminaire'},
        '4': {
                'address': 'ffffffffffff',
                'fixtureId': 859,
                'groupId': 0,
                'id': 4,
                'image': 'FFFFFFFFF',
                'name': 'Foo/Baar',
                'position': 2,
                'type': 'Luminaire'},
        '9': {
                'address': 'ffffffffffff',
                'fixtureId': 859,
                'groupId': 0,
                'id': 9,
                'image': 'FFFFFFFFF',
                'name': 'Foo',
                'position': 6,
                'type': 'Luminaire'}}
        '''
        """
        LOGGER.debug(f"__process_units - Processing units {pformat(units)}")

        for unit_id in units:
            tmp = units[unit_id]
            key = f"{self._network_id}-{unit_id}"

            type = None

            if "type" in tmp:
                type = tmp["type"]

            unit = Unit(
                name=tmp["name"].strip(),
                address=tmp["address"],
                type=type,
                unit_id=unit_id,
                wire_id=self._wire_id,
                network_id=self._network_id,
                controller=self._controller,
                controls=[],
            )
            self.units[key] = unit
