"""State representation of Casanbi Unit"""

import logging
import re

from pprint import pformat
from typing import Tuple, Union
from colorsys import rgb_to_hsv

from .errors import AiocasambiException
from .consts import STATE_RUNNING


LOGGER = logging.getLogger(__name__)

UNIT_STATE_OFF = "off"
UNIT_STATE_ON = "on"


class Unit:
    """Represents a client network device."""

    def __init__(
        self,
        *,
        name: str,
        address: str,
        type: str,
        unit_id: int,
        network_id: int,
        wire_id: int,
        controller,
        controls: dict,
        value: float = 0,
        distribution: float = 0,
        fixture_id: int = 0,
        online: bool = True,
        enabled: bool = True,
        state: str = UNIT_STATE_OFF,
    ):
        self._name = name.strip()
        self._address = address
        self._unit_id = int(unit_id)
        self._fixture_id = int(fixture_id)
        self._network_id = network_id
        self._value = value
        self._distribution = distribution
        self._state = state
        self._type = type
        self._fixture_model = None
        self._fixture = None
        self._wire_id = wire_id
        self._controller = controller
        self._oem = None
        self._online = online
        self._enabled = enabled
        self._firmware_version = None

        self._controls = {}
        for control in controls:
            key = control["type"]
            self._controls[key] = control

    @property
    def value(self) -> float:
        """
        Getter for value
        """
        value = 0

        if "Dimmer" in self._controls:
            return self._controls["Dimmer"]["value"]
        else:
            err_msg = f"unit_id={self._unit_id} - value - "
            err_msg += f"Dimmer is missing in controls: {self._controls}"

            LOGGER.debug(err_msg)

            return value

    @value.setter
    def value(self, value: float) -> None:
        """
        Setter for value
        """
        LOGGER.debug(f"unit_id={self._unit_id} - value - setting value to: {value}")
        if value == 0:
            self._state = UNIT_STATE_OFF
            self._value = value
        elif value > 0 and value <= 1:
            self._state = UNIT_STATE_ON
            self._value = value
        else:
            raise AiocasambiException(f"invalid value {value} for {self}")

    @property
    def distribution(self) -> float:
        """
        Getter for distribution
        """
        distribution = 0

        if "Vertical" in self._controls:
            return self._controls["Vertical"]["value"]
        else:
            err_msg = f"unit_id={self._unit_id} - distribution - "
            err_msg += f"Vertical is missing in controls: {self._controls}"

            LOGGER.debug(err_msg)

            return distribution

    @distribution.setter
    def distribution(self, distribution: float) -> None:
        """
        Setter for distribution
        """
        LOGGER.debug(
            f"unit_id={self._unit_id} - distribution - setting distribution to: {distribution}"
        )
        if distribution >= 0 and distribution <= 1:
            self._distribution = distribution
        else:
            raise AiocasambiException(f"invalid distribution {distribution} for {self}")

    @property
    def name(self) -> str:
        """
        Getter for name
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        """
        Setter for name
        """
        self._name = name.strip()

    @property
    def type(self) -> str:
        """
        Getter for type
        """
        return self._type

    @type.setter
    def type(self, type: str) -> None:
        """
        Setter for name
        """
        self._type = type

    @property
    def fixture_model(self) -> str:
        """
        Getter for fixture model
        """
        return self._fixture_model

    @fixture_model.setter
    def fixture_model(self, fixture_model: str) -> None:
        """
        Setter for fixture model
        """
        self._fixture_model = fixture_model

    @property
    def fixture_id(self) -> str:
        """
        Getter for fixture id
        """
        return self._fixture_id

    @fixture_id.setter
    def fixture_id(self, fixture_id: int) -> None:
        """
        Setter for fixture model
        """
        self._fixture_id = fixture_id

    @property
    def online(self) -> bool:
        """
        Getter for online
        """
        if (
            self.controller.get_websocket_state(network_id=self._network_id)
            != STATE_RUNNING
        ):
            # Return false if websocket isnt online
            LOGGER.debug(f"websocket is offline for unit_id: {self._unit_id}")
            return False

        return self._online

    @online.setter
    def online(self, online: bool) -> None:
        """
        Setter for online
        """
        if not self._online and online:
            LOGGER.info(f"unit_id={self._unit_id} - online - unit is back online")
        elif self._online and not online:
            LOGGER.debug(f"unit_id={self._unit_id} - online - Setting unit to offline")
        self._online = online

    @property
    def controls(self) -> dict:
        """
        Getter for controls state
        """
        return self._controls

    @controls.setter
    def controls(self, controls: Union[list, dict]) -> None:
        """
        Setter for controls
        """
        if isinstance(controls, list):
            for control in controls:
                # Recusive call
                self.controls = control
        elif isinstance(controls, dict):
            dbg_msg = f"unit_id={self._unit_id} - setter controls"
            dbg_msg += f" - Adding following control to controls: {controls}"
            LOGGER.debug(dbg_msg)

            key = controls["type"]
            self._controls[key] = controls

    @property
    def firmware_version(self) -> str:
        """
        Getter for firmware_version
        """

        return self._firmware_version

    @firmware_version.setter
    def firmware_version(self, firmware_version) -> None:
        """
        Setter for firmware_version
        """
        self._firmware_version = firmware_version

    @property
    def oem(self) -> str:
        """
        Getter for oem
        """
        return self._oem

    @oem.setter
    def oem(self, oem: str) -> None:
        """
        Setter for oem
        """
        self._oem = oem

    @property
    def fixture(self) -> str:
        """
        Getter for fixture
        """
        return self._fixture

    @fixture.setter
    def fixture(self, fixture: str) -> None:
        """
        Setter for fixture
        """
        self._fixture = fixture

    @property
    def enabled(self) -> bool:
        """
        Getter for enabled
        """
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        """
        Setter for enabled
        """
        self._enabled = enabled

    @property
    def state(self) -> str:
        """
        Getter for state
        """
        return self._state

    @state.setter
    def state(self, state: str) -> None:
        """
        Setter for state
        """
        if state == UNIT_STATE_OFF:
            self.value = 0
        self._state = state

    @property
    def unique_id(self) -> str:
        """
        Getter for unique_id
        """
        unique_id = None

        if self._address:
            unique_id = f"{self._network_id}-{self._address}"
        else:
            # Use unit id as fallback
            unique_id = f"{self._network_id}-{self._unit_id}"

        return unique_id

    @property
    def controller(self):
        """
        Getter for controller
        """

        return self._controller

    @controller.setter
    def controller(self, controller):
        """
        Setter for controller
        """
        self._controller = controller

    @property
    def address(self):
        """
        Getter for address
        """
        return self._address

    @property
    def unit_id(self):
        """
        Getter for unit_id
        """
        return self._unit_id

    async def turn_unit_off(self) -> None:
        """
        Function for turning a unit off
        """
        # Unit_id needs to be an integer
        unit_id = self._unit_id
        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            raise AiocasambiException(
                f"expected unit_id to be an integer, got: {unit_id}"
            )

        target_controls = {"Dimmer": {"value": 0}}

        message = {
            "wire": self._wire_id,
            "method": "controlUnit",
            "id": unit_id,
            "targetControls": target_controls,
        }

        await self._controller.ws_send_message(message, network_id=self._network_id)

    async def turn_unit_on(self) -> None:
        """
        Function for turning a unit on

        Response on ok:
        {'wire': 1, 'method': 'peerChanged', 'online': True}
        """
        unit_id = self._unit_id

        # Unit_id needs to be an integer
        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            reason = "expected unit_id to be an integer,"
            reason += f"got: {unit_id}"
            raise AiocasambiException(reason)

        target_controls = {"Dimmer": {"value": 1}}

        message = {
            "wire": self._wire_id,
            "method": "controlUnit",
            "id": unit_id,
            "targetControls": target_controls,
        }

        await self._controller.ws_send_message(message, network_id=self._network_id)

    def set_wire_id(self, *, wire_id: str) -> None:
        """
        Setter for wire_id
        """
        self._wire_id = wire_id

    async def set_unit_rgbw(self, *, color_value: Tuple[int, int, int]) -> None:
        """
        Set RGB
        """
        target_controls = None
        (red, green, blue, white) = color_value

        unit_id = self._unit_id

        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            raise AiocasambiException(
                f"expected unit_id to be an integer, got: {unit_id}"
            )

        white_value = white / 255.0
        # 'name': 'white', 'type': 'White', 'value': 0.0
        target_controls = {
            "RGB": {"rgb": f"rgb({red}, {green}, {blue})"},
            "Colorsource": {"source": "RGB"},
            "White": {"value": white_value},
        }

        message = {
            "wire": self._wire_id,
            "method": "controlUnit",
            "id": unit_id,
            "targetControls": target_controls,
        }

        dbg_msg = f"Setting color to rgb({red}, {green}, {blue}, {white}) "
        dbg_msg += f"sending: {pformat(message)}"
        LOGGER.debug(f"unit_id={self._unit_id} - set_unit_rgb - {dbg_msg}")

        await self._controller.ws_send_message(message, network_id=self._network_id)
        return

    async def set_unit_rgb(
        self, *, color_value: Tuple[int, int, int], send_rgb_format=False
    ) -> None:
        """
        Set RGB
        """
        target_controls = None
        (red, green, blue) = color_value
        (hue, sat, value) = rgb_to_hsv(red, green, blue)

        unit_id = self._unit_id

        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            raise AiocasambiException(
                f"expected unit_id to be an integer, got: {unit_id}"
            )

        if not send_rgb_format:
            target_controls = {
                "RGB": {"hue": round(hue, 1), "sat": round(sat, 1)},
                "Colorsource": {"source": "RGB"},
            }
        else:
            target_controls = {
                "RGB": {"rgb": f"rgb({red}, {green}, {blue})"},
                "Colorsource": {"source": "RGB"},
            }

        message = {
            "wire": self._wire_id,
            "method": "controlUnit",
            "id": unit_id,
            "targetControls": target_controls,
        }

        dbg_msg = f"Setting color to rgb({red}, {green}, {blue}) "
        dbg_msg += f"- (hue: {hue}, sat: {sat}, value: {value}) - "
        dbg_msg += f"- send_rgb_format: {send_rgb_format} - "
        dbg_msg += f"sending: {pformat(message)}"
        LOGGER.debug(f"unit_id={self._unit_id} - set_unit_rgb - {dbg_msg}")

        await self._controller.ws_send_message(message, network_id=self._network_id)
        return

    async def set_unit_color_temperature(self, *, value: int, source="TW") -> None:
        """
        Setter for unit color temperature
        """
        # Unit_id needs to be an integer
        unit_id = self._unit_id

        target_value = value
        if source == "mired":
            # Convert to Kelvin
            target_value = round(1000000 / value)

        # Convert to nerest 50 in kelvin, like the gui is doing
        if target_value % 50 != 0:
            target_value = int(target_value / 50) * 50 + 50

            dbg_msg = f"converting target value to {target_value}"
            dbg_msg += " (nearest 50 kelvin like GUI)"
            LOGGER.debug(
                f"unit_id={self._unit_id} - set_unit_color_temperature - {dbg_msg}"
            )

        # Get min and max temperature color in kelvin
        (cct_min, cct_max, _) = self.get_supported_color_temperature()
        if target_value < cct_min:
            dbg_msg = f"target_value: {target_value}"
            dbg_msg += " smaller than min supported temperature,"
            dbg_msg += " setting to min supported color temperature:"
            dbg_msg += f" {cct_min}"
            LOGGER.debug(
                f"unit_id={self._unit_id} - set_unit_color_temperature - {dbg_msg}"
            )

            target_value = cct_min
        elif target_value > cct_max:
            dbg_msg = f"target_value: {target_value}"
            dbg_msg += " larger than max supported temperature,"
            dbg_msg += " setting to max supported color temperature:"
            dbg_msg += f" {cct_max}"
            LOGGER.debug(
                f"unit_id={self._unit_id} - set_unit_color_temperature - {dbg_msg}"
            )

            target_value = cct_max

        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            raise AiocasambiException(
                f"expected unit_id to be an integer, got: {unit_id}"
            )

        target_controls = {
            "ColorTemperature": {"value": target_value},
            "Colorsource": {"source": "TW"},
        }

        message = {
            "wire": self._wire_id,
            "method": "controlUnit",
            "id": unit_id,
            "targetControls": target_controls,
        }

        dbg_msg = f"value: {value}, source: {source} "
        dbg_msg += f"sending: {message}"
        LOGGER.debug(
            f"unit_id={self._unit_id} - set_unit_color_temperature - {dbg_msg}"
        )

        await self._controller.ws_send_message(message, network_id=self._network_id)

    async def set_unit_value(self, *, value: Union[float, int]) -> None:
        """
        Function for setting an unit to a specific value

        Response on ok:
        {'wire': 1, 'method': 'peerChanged', 'online': True}
        """
        unit_id = self._unit_id

        # Unit_id needs to be an integer
        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            raise AiocasambiException(
                f"expected unit_id to be an integer, got: {unit_id}"
            )

        if not (value >= 0 and value <= 1):
            raise AiocasambiException("value needs to be between 0 and 1")

        target_controls = {"Dimmer": {"value": value}}

        message = {
            "wire": self._wire_id,
            "method": "controlUnit",
            "id": unit_id,
            "targetControls": target_controls,
        }

        self.value = value

        LOGGER.debug(f"unit_id={self._unit_id} - set_unit_value - value={value}")

        await self._controller.ws_send_message(message, network_id=self._network_id)

    async def set_unit_distribution(self, *, distribution: Union[float, int]) -> None:
        """
        Function for setting an unit to a specific distribution position

        Response on ok:
        {'wire': 1, 'method': 'peerChanged', 'online': True}
        """
        unit_id = self._unit_id

        # Unit_id needs to be an integer
        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            raise AiocasambiException(
                f"expected unit_id to be an integer, got: {unit_id}"
            )

        if not (distribution >= 0 and distribution <= 1):
            raise AiocasambiException("distribution needs to be between 0 and 1")

        target_controls = {"Vertical": {"value": distribution}}

        message = {
            "wire": self._wire_id,
            "method": "controlUnit",
            "id": unit_id,
            "targetControls": target_controls,
        }

        self.distribution = distribution

        LOGGER.debug(
            f"unit_id={self._unit_id} - set_unit_distribution - distribution={distribution}"
        )

        await self._controller.ws_send_message(message, network_id=self._network_id)

    async def set_unit_target_controls(self, *, target_controls) -> None:
        """
        Function for setting an unit to specific controls

        Response on ok:
        {'wire': 1, 'method': 'peerChanged', 'online': True}
        """
        value = None
        distribution = None
        unit_id = self._unit_id

        # Unit_id needs to be an integer
        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            raise AiocasambiException(
                f"expected unit_id to be an integer, got: {unit_id}"
            )

        message = {
            "wire": self._wire_id,
            "method": "controlUnit",
            "id": unit_id,
            "targetControls": target_controls,
        }

        if "Dimmer" in target_controls:
            value = target_controls["Dimmer"]["value"]
            self.value = value

        if "Vertical" in target_controls:
            distribution = target_controls["Vertical"]["value"]
            self.distribution = distribution

        LOGGER.debug(
            f"unit_id={self._unit_id} - set_unit_target controls - value={value}, distribution={distribution}"
        )

        await self._controller.ws_send_message(message, network_id=self._network_id)

    def get_supported_color_temperature(self) -> Tuple[int, int, int]:
        """
        Return the supported color temperatures,
        (0, 0, 0) if nothing is supported
        """
        cct_min = 0
        cct_max = 0
        current = 0

        if not self._controls:
            LOGGER.debug(f"unit_id={self._unit_id} control is None")
            return (min, max, current)

        if "CCT" in self._controls and self._controls["CCT"]:
            cct_min = self._controls["CCT"]["min"]
            cct_max = self._controls["CCT"]["max"]
            current = self._controls["CCT"]["value"]

        dbg_msg = "returning "
        dbg_msg += f"min={cct_min} max={cct_max} current={current} "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(
            f"unit_id={self._unit_id} - get_supported_color_temperature - {dbg_msg}"
        )

        return (cct_min, cct_max, current)

    def get_max_mired(self) -> int:
        """
        M = 1000000 / T

        25000 K, has a mired value of M = 40 mireds
        1000000 / 25000 = 40

        {
            'Dimmer': {
                'type': 'Dimmer',
                'value': 0.0
                },
            'CCT': {
                'min': 2200,
                'max': 6000,
                'level': 0.4631578947368421,
                'type': 'CCT',
                'value': 3960.0
                }
        }
        """
        cct_min = self._controls["CCT"]["min"]
        result = round(1000000 / cct_min)

        dbg_msg = f"returning {result} (in kv {cct_min}) "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(f"unit_id={self._unit_id} - get_max_mired - {dbg_msg}")

        return result

    def get_min_mired(self) -> int:
        """
        M = 1000000 / T

        25000 K, has a mired value of M = 40 mireds
        1000000 / 25000 = 40

        {
            'Dimmer': {
                'type': 'Dimmer',
                'value': 0.0
                },
            'CCT': {
                'min': 2200,
                'max': 6000,
                'level': 0.4631578947368421,
                'type': 'CCT',
                'value': 3960.0
                }
        }
        """
        cct_max = self._controls["CCT"]["max"]
        result = round(1000000 / cct_max)

        dbg_msg = f"returning {result} (in kv {cct_max}) "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(f"unit_id={self._unit_id} - get_min_mired  - {dbg_msg}")

        return result

    def get_color_temp(self) -> int:
        """
        M = 1 000 000 / T

        25000 K, has a mired value of M = 40 mireds
        1000000 / 25000 = 40

        {
            'Dimmer': {
                'type': 'Dimmer',
                'value': 0.0
                },
            'CCT': {
                'min': 2200,
                'max': 6000,
                'level': 0.4631578947368421,
                'type': 'CCT',
                'value': 3960.0
                }
        }
        """
        cct_value = self._controls["CCT"]["value"]
        result = round(1000000 / cct_value)

        dbg_msg = f"returning {result} (in kv {cct_value}) "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(f"unit_id={self._unit_id} - get_color_temp - {dbg_msg}")

        return result

    def get_rgb_color(self) -> Tuple[int, int, int]:
        """
        Return rgb color

        {
            'Color': {'sat': 1.0, 'name': 'rgb', 'hue': 1.0, 'rgb': 'rgb(255,  0,  4)'
        }
        """
        red = 0
        green = 0
        blue = 0

        regexp = re.compile(
            r"rgb\(\s*(?P<red>\d+),\s+(?P<green>\d+),\s+(?P<blue>\d+)\)"
        )
        rgb_value = self._controls["Color"]["rgb"]

        match = regexp.match(rgb_value)

        if match:
            red = int(match.group("red"))
            green = int(match.group("green"))
            blue = int(match.group("blue"))
        else:
            err_msg = f"failed to parse rgb_value: {rgb_value}"

            LOGGER.error(f"unit_id={self._unit_id} - get_rgb_color - {err_msg}")

        dbg_msg = f"returning ({red}, {green}, {blue}) "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(f"unit_id={self._unit_id} - get_rgb_color - {dbg_msg}")

        return (red, green, blue)

    def get_rgbw_color(self) -> Tuple[int, int, int, int]:
        """
        Return rgbw color
        """
        (red, green, blue) = self.get_rgb_color()

        white = self._controls["White"]["value"]

        return (red, green, blue, int(round(white * 255, 0)))

    def supports_rgbw(self) -> bool:
        """
        Returns true if unit supports color temperature

        {
            'activeSceneId': 0,
            'address': 'ffffff',
            'condition': 0,
            'controls': [[{'name': 'dimmer0', 'type': 'Dimmer', 'value': 0.0},
                        {'hue': 0.9882697947214076,
                            'name': 'rgb',
                            'rgb': 'rgb(255, 21, 40)',
                            'sat': 0.9176470588235294,
                            'type': 'Color'},
                        {'name': 'white', 'type': 'White', 'value': 0.0}]],
            'dimLevel': 0.0,
            'firmwareVersion': '26.24',
            'fixtureId': 4027,
            'groupId': 0,
            'id': 14,
            'name': 'Test RGB',
            'on': True,
            'online': True,
            'position': 10,
            'priority': 3,
            'status': 'ok',
            'type': 'Luminaire'}

        """
        if not self._controls:
            LOGGER.debug(f"unit_id={self._unit_id} - supports_rgbw - controls is None")
            return False

        if "Color" in self._controls and "White" in self._controls:
            return True
        return False

    def supports_rgb(self) -> bool:
        """
        Returns true if unit supports color temperature

        {
            'activeSceneId': 0,
            'address': 'ffffff',
            'condition': 0,
            'controls': [[{'name': 'dimmer0', 'type': 'Dimmer', 'value': 0.0},
                        {'hue': 0.9882697947214076,
                            'name': 'rgb',
                            'rgb': 'rgb(255, 21, 40)',
                            'sat': 0.9176470588235294,
                            'type': 'Color'},
                        {'name': 'white', 'type': 'White', 'value': 0.0}]],
            'dimLevel': 0.0,
            'firmwareVersion': '26.24',
            'fixtureId': 4027,
            'groupId': 0,
            'id': 14,
            'name': 'Test RGB',
            'on': True,
            'online': True,
            'position': 10,
            'priority': 3,
            'status': 'ok',
            'type': 'Luminaire'}

        """
        if not self._controls:
            LOGGER.debug(f"unit_id={self._unit_id} - supports_rgb - controls is None")
            return False

        if "Color" in self._controls:
            return True
        return False

    def supports_color_temperature(self) -> bool:
        """
        Returns true if unit supports color temperature

        {
            'activeSceneId': 0,
            'address': 'ffffffffffff',
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
            'image': 'ffffffffffffffffffffffffffffffff',
            'name': 'Arbetslampa',
            'on': True,
            'online': True,
            'position': 9,
            'priority': 3,
            'status': 'ok',
            'type': 'Luminaire'
        }

        """
        if not self._controls:
            LOGGER.debug(
                f"unit_id={self._unit_id} - supports_color_temperature - controls is None"
            )
            return False

        if "CCT" in self._controls:
            return True
        return False

    def supports_brightness(self) -> bool:
        """
        Returns true if unit supports color temperature

        {
            'activeSceneId': 0,
            'address': 'ffffffffffff',
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
            'image': 'ffffffffffffffffffffffffffffffff',
            'name': 'Arbetslampa',
            'on': True,
            'online': True,
            'position': 9,
            'priority': 3,
            'status': 'ok',
            'type': 'Luminaire'
        }

        """
        if not self._controls:
            LOGGER.debug(
                f"unit_id={self._unit_id} - supports_brightness - controls is None"
            )
            return False

        if "Dimmer" in self._controls:
            return True
        return False

    def supports_distribution(self) -> bool:
        """
        Returns true if unit supports distribution

        {
            'activeSceneId': 0,
            'address': 'ffffffffffff',
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
            'image': 'ffffffffffffffffffffffffffffffff',
            'name': 'Arbetslampa',
            'on': True,
            'online': True,
            'position': 9,
            'priority': 3,
            'status': 'ok',
            'type': 'Luminaire'
        }

        """
        if not self._controls:
            LOGGER.debug(
                f"unit_id={self._unit_id} - supports_distribution - controls is None"
            )
            return False

        if "Vertical" in self._controls:
            return True
        return False

    def is_light(self) -> bool:
        """Check if the unit is a light fixture"""
        if self._type == "Luminaire":
            return True
        elif self._type == "Driver":
            return True
        elif self._type == "BatterySwitch":
            return False
        return False

    def __repr__(self) -> str:
        """Return the representation."""
        name = self._name

        address = self._address

        unit_id = self._unit_id
        network_id = self._network_id

        value = self._value
        state = self._state

        wire_id = self._wire_id

        result = f"<Unit {name}:"
        result += f"unit_id={unit_id} "
        result += f"fixture_id={self._fixture_id} "
        result += f"oem={self._oem} "
        result += f"fixture_model={self._fixture_model} "
        result += f"type={self._type} "
        result += f"address={address} "

        if self._type:
            result += f"type={self._type} "

        result += f"value={value} "
        if self.supports_distribution():
            result += f"distribution={self._distribution} "
        result += f"state={state} "
        result += f"online={self.online} "
        result += f"network_id={network_id} "
        result += f"wire_id={wire_id}"

        if self._fixture:
            result = f"{result} fixure={self._fixture}"

        if self._firmware_version:
            result = f"{result} firmware_version={self._firmware_version}"

        result = f"{result} is_light={self.is_light()}"

        if self._controls:
            # Controls state is set, not None
            result = f"{result} supports_brightness="
            result = f"{result}{self.supports_brightness()}"

            result = f"{result} supports_distribution="
            result = f"{result}{self.supports_distribution()}"

            result = f"{result} supports_color_temperature="
            result = f"{result}{self.supports_color_temperature()}"

            result = f"{result} supports_rgb="
            result = f"{result}{self.supports_rgb()}"

            result = f"{result} supports_rgbw="
            result = f"{result}{self.supports_rgbw()}"

            result = f"{result} controls={self._controls}"

        websocket_state = self.controller.get_websocket_state(
            network_id=self._network_id
        )
        result = f"{result} websocket_state={websocket_state}"
        result = f"{result} >"

        return result
