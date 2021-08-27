"""State representation of Casanbi Unit"""

import logging

from pprint import pformat
from typing import Tuple
from .errors import AiocasambiException

LOGGER = logging.getLogger(__name__)

UNIT_STATE_OFF = 'off'
UNIT_STATE_ON = 'on'


class Unit():
    """Represents a client network device."""

    def __init__(
            self,
            *,
            name,
            address,
            unit_id,
            network_id,
            wire_id,
            controller,
            controls,
            value=0,
            online=True,
            enabled=True,
            state=UNIT_STATE_OFF
    ):
        self._name = name
        self._address = address
        self._unit_id = unit_id
        self._network_id = network_id
        self._value = value
        self._state = state
        self._fixture_model = None
        self._fixture = None
        self._wire_id = wire_id
        self._controller = controller
        self._oem = None
        self._online = online
        self._enabled = enabled

        self._controls = {}
        for control in controls:
            key = control['type']
            self._controls[key] = control

    @property
    def value(self):
        '''
        Getter for value
        '''

        try:
            return self._controls['Dimmer']['value']
        except KeyError as err:
            err_msg = f"unit_id={self._unit_id} - value - "
            err_msg += f"caught KeyError unit: {self} err: {err}"

            LOGGER.debug(err)

            raise AiocasambiException(err)

    @value.setter
    def value(self, value):
        '''
        Setter for value
        '''
        LOGGER.debug(
            f"unit_id={self._unit_id} - value - setting value to: {value}")
        if value == 0:
            self._state = UNIT_STATE_OFF
            self._value = value
        elif value > 0 and value <= 1:
            self._state = UNIT_STATE_ON
            self._value = value
        else:
            raise AiocasambiException(f"invalid value {value} for {self}")

    @property
    def name(self):
        '''
        Getter for name
        '''
        return self._name

    @name.setter
    def name(self, name):
        '''
        Setter for name
        '''
        self._name = name

    @property
    def fixture_model(self):
        '''
        Getter for fixture model
        '''
        return self._fixture_model

    @fixture_model.setter
    def fixture_model(self, fixture_model):
        '''
        Setter for fixture model
        '''
        self._fixture_model = fixture_model

    @property
    def online(self):
        '''
        Getter for online
        '''
        return self._online

    @online.setter
    def online(self, online):
        '''
        Setter for online
        '''
        if not self._online and online:
            LOGGER.info(
                f"unit_id={self._unit_id} - online - unit is back online")
        elif self._online and not online:
            LOGGER.debug(
                f"unit_id={self._unit_id} - online - Setting unit to offline")
        self._online = online

    @property
    def controls(self):
        '''
        Getter for controls state
        '''
        return self._controls

    @controls.setter
    def controls(self, controls):
        '''
        Setter for controls
        '''
        if isinstance(controls, list):
            for control in controls:
                # Recusive call
                self.controls = control
        elif isinstance(controls, dict):
            LOGGER.debug(
                f"unit_id={self._unit_id} - setter controls - Adding following control to controls: {controls}")
            key = controls['type']
            self._controls[key] = controls

    @property
    def oem(self):
        '''
        Getter for oem
        '''
        return self._oem

    @oem.setter
    def oem(self, oem):
        '''
        Setter for oem
        '''
        self._oem = oem

    @property
    def fixture(self):
        '''
        Getter for fixture
        '''
        return self._fixture

    @fixture.setter
    def fixture(self, fixture):
        '''
        Setter for fixture
        '''
        self._fixture = fixture

    @property
    def enabled(self):
        '''
        Getter for enabled
        '''
        return self._enabled

    @enabled.setter
    def enabled(self, enabled):
        '''
        Setter for enabled
        '''
        self._enabled = enabled

    @property
    def state(self):
        '''
        Getter for state
        '''
        return self._state

    @state.setter
    def state(self, state):
        '''
        Setter for state
        '''
        if state == UNIT_STATE_OFF:
            self.value = 0
        self._state = state

    @property
    def unique_id(self):
        '''
        Getter for unique_id
        '''

        return f"{self._network_id}-{self._unit_id}"

    @property
    def controller(self):
        '''
        Getter for controller
        '''

        return self._controller

    @controller.setter
    def controller(self, controller):
        '''
        Setter for controller
        '''
        self._controller = controller

    async def turn_unit_off(self):
        '''
        Function for turning a unit off
        '''
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
                f"expected unit_id to be an integer, got: {unit_id}")

        target_controls = {'Dimmer': {'value': 0}}

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        await self._controller.ws_send_message(message)

    async def turn_unit_on(self):
        '''
        Function for turning a unit on

        Response on ok:
        {'wire': 1, 'method': 'peerChanged', 'online': True}
        '''
        unit_id = self._unit_id

        # Unit_id needs to be an integer
        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            reason = 'expected unit_id to be an integer,'
            reason += f"got: {unit_id}"
            raise AiocasambiException(reason)

        target_controls = {'Dimmer': {'value': 1}}

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        await self._controller.ws_send_message(message)

    async def set_unit_rgb(self, value: Tuple[int, int, int]):
        (red, green, blue) = value

        unit_id = self._unit_id

        target_controls = {
            'RGB': {'rgb': f"rgb({red}, {green}, {blue})"},
            'Colorsource': {'source': 'RGB'}
        }

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        dbg_msg = f"Setting color to rgb({red}, {green}, {blue}) - "
        dbg_msg += f"sending: {message}"
        LOGGER.debug(
            f"unit_id={self._unit_id} - set_unit_rgb - {dbg_msg}")

        await self._controller.ws_send_message(message)
        return

    async def set_unit_color_temperature(self, *,
                                         value: int,
                                         source="TW"):
        '''
        Setter for unit color temperature
        '''
        # Unit_id needs to be an integer
        unit_id = self._unit_id

        target_value = value
        if source == 'mired':
            # Convert to Kelvin
            target_value = round(1000000 / value)

        # Convert to nerest 50 in kelvin, like the gui is doing
        if target_value % 50 != 0:
            target_value = int(target_value/50)*50+50

            dbg_msg = f"converting target value to {target_value}"
            dbg_msg += ' (nearest 50 kelvin like GUI)'
            LOGGER.debug(
                f"unit_id={self._unit_id} - set_unit_color_temperature - {dbg_msg}")

        # Get min and max temperature color in kelvin
        (cct_min, cct_max, _) = self.get_supported_color_temperature()
        if target_value < cct_min:
            dbg_msg = f"target_value: {target_value}"
            dbg_msg += ' smaller than min supported temperature,'
            dbg_msg += ' setting to min supported color temperature:'
            dbg_msg += f" {cct_min}"
            LOGGER.debug(
                f"unit_id={self._unit_id} - set_unit_color_temperature - {dbg_msg}")

            target_value = cct_min
        elif target_value > cct_max:
            dbg_msg = f"target_value: {target_value}"
            dbg_msg += ' larger than max supported temperature,'
            dbg_msg += ' setting to max supported color temperature:'
            dbg_msg += f" {cct_max}"
            LOGGER.debug(
                f"unit_id={self._unit_id} - set_unit_color_temperature - {dbg_msg}")

            target_value = cct_max

        if isinstance(unit_id, int):
            pass
        elif isinstance(unit_id, str):
            unit_id = int(unit_id)
        elif isinstance(unit_id, float):
            unit_id = int(unit_id)
        else:
            raise AiocasambiException(
                "expected unit_id to be an integer, got: {}".format(unit_id))

        target_controls = {
            'ColorTemperature': {'value': target_value},
            'Colorsource': {'source': 'TW'}
        }

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        dbg_msg = f"value: {value}, source: {source} "
        dbg_msg += f"sending: {message}"
        LOGGER.debug(
            f"unit_id={self._unit_id} - set_unit_color_temperature - {dbg_msg}")

        await self._controller.ws_send_message(message)

    async def set_unit_value(self, *, value):
        '''
        Function for setting an unit to a specific value

        Response on ok:
        {'wire': 1, 'method': 'peerChanged', 'online': True}
        '''
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
                "expected unit_id to be an integer, got: {}".format(unit_id))

        if not(value >= 0 and value <= 1):
            raise AiocasambiException('value needs to be between 0 and 1')

        target_controls = {'Dimmer': {'value': value}}

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        self.value = value

        LOGGER.debug(
            f"unit_id={self._unit_id} - set_unit_value - value={value}")

        await self._controller.ws_send_message(message)

    def get_supported_color_temperature(self):
        '''
        Return the supported color temperatures,
        (0, 0, 0) if nothing is supported
        '''
        cct_min = 0
        cct_max = 0
        current = 0

        if not self._controls:
            LOGGER.debug(f"unit_id={self._unit_id} control is None")
            return (min, max, current)

        if 'CCT' in self._controls and self._controls['CCT']:
            cct_min = self._controls['CCT']['min']
            cct_max = self._controls['CCT']['max']
            current = self._controls['CCT']['value']

        dbg_msg = 'returning '
        dbg_msg += f"min={cct_min} max={cct_max} current={current} "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(
            f"unit_id={self._unit_id} - get_supported_color_temperature - {dbg_msg}")

        return (cct_min, cct_max, current)

    def get_max_mired(self) -> int:
        '''
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
        '''
        cct_min = self._controls['CCT']['min']
        result = round(1000000/cct_min)

        dbg_msg = f"returning {result} (in kv {cct_min}) "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(f"unit_id={self._unit_id} - get_max_mired - {dbg_msg}")

        return result

    def get_min_mired(self) -> int:
        '''
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
        '''
        cct_max = self._controls['CCT']['max']
        result = round(1000000/cct_max)

        dbg_msg = f"returning {result} (in kv {cct_max}) "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(f"unit_id={self._unit_id} - get_min_mired  - {dbg_msg}")

        return result

    def get_color_temp(self):
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
        cct_value = self._controls['CCT']['value']
        result = round(1000000/cct_value)

        dbg_msg = f"returning {result} (in kv {cct_value}) "
        dbg_msg += f"for name={self.name}"
        LOGGER.debug(f"unit_id={self._unit_id} - get_color_temp - {dbg_msg}")

        return result

    def supports_rgb(self) -> bool:
        '''
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

        '''
        if not self._controls:
            LOGGER.debug(
                f"unit_id={self._unit_id} - supports_rgb - controls is None")
            return False

        if 'Color' in self._controls:
            return True
        return False

    def supports_color_temperature(self) -> bool:
        '''
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

        '''
        if not self._controls:
            LOGGER.debug(
                f"unit_id={self._unit_id} - supports_color_temperature - controls is None")
            return False

        if 'CCT' in self._controls:
            return True
        return False

    def supports_brightness(self) -> bool:
        '''
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

        '''
        if not self._controls:
            LOGGER.debug(
                f"unit_id={self._unit_id} - supports_brightness - controls is None")
            return False

        if 'Dimmer' in self._controls:
            return True
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
        result += f"address={address} "
        result += f"value={value} "
        result += f"state={state} "
        result += f"online={self._online} "
        result += f"network_id={network_id} "
        result += f"wire_id={wire_id}"

        if self._fixture:
            result = f"{result} fixure={self._fixture}"

        if self._fixture_model:
            result = f"{result} fixture_model={self._fixture_model}"

        if self._oem:
            result = f"{result} oem={self._oem}"

        if self._controls:
            # Controls state is set, not None
            result = f"{result} supports_brightness="
            result = f"{result}{self.supports_brightness()}"

            result = f"{result} supports_color_temperature="
            result = f"{result}{self.supports_color_temperature()}"

            result = f"{result} supports_rgb="
            result = f"{result}{self.supports_rgb()}"

            result = f"{result} controls={self._controls}"

        result = f"{result} >"

        return result
