"""State representation of Casanbi Unit"""

import logging

from .errors import AiocasambiException
from pprint import pformat

LOGGER = logging.getLogger(__name__)

UNIT_STATE_OFF = 'off'
UNIT_STATE_ON = 'on'


class Units():
    '''
    Class for representing Casambi Units
    '''

    def __init__(
        self,
        units: set,
        *,
        network_id,
        wire_id,
        controller,
        online=True
    ) -> None:
        self._network_id = network_id
        self._wire_id = wire_id
        self._controller = controller
        self.units = {}
        self._online = online

        self.__process_units(units)

    def handle_peer_changed(self, message: dict):
        '''
        Function for handling peer change
        '''
        changes = {}
        if 'online' in message:
            self.online = message['online']

        for key, unit in self.units.items():
            changes[key] = unit

        return changes

    def process_network_state(self, data):
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
            if 'units' not in data:
                # Safe guard
                return
        except TypeError as err:
            LOGGER.error(f"process_network_state: unknown data: {data}")
            raise err

        for unit_key in data['units']:
            unit_data = data['units'][unit_key]
            key = f"{self._network_id}-{unit_key}"

            self.units[key].online = unit_data['online']
            self.units[key].name = unit_data['name']
            if unit_data['online']:
                self.units[key].value = unit_data['dimLevel']

    def process_unit_event(self, msg):
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

        LOGGER.debug(f"process_unit_event Processing msg: {msg}")

        if 'id' not in msg:
            error_msg = 'processing_unit_event discarding message, '
            error_msg += f"id is missing in msg: {msg}"

            LOGGER.error(error_msg)

            return

        key = f"{self._network_id}-{msg['id']}"

        if 'online' in msg and not msg['online']:
            LOGGER.debug(f"Gateway is not online msg{msg}")

        if 'method' in msg and msg['method'] == 'unitChanged':
            controls = msg['controls']
            for control in controls:

                LOGGER.debug(f"method \"unitChanged\" control: {control}")

                if 'type' in control and control['type'] == 'Dimmer':
                    name = ''
                    if 'details' in msg and 'name' in msg['details']:
                        name = (msg['details']['name']).strip()
                    elif 'name' in msg:
                        name = (msg['name']).strip()

                    dbg_msg = f"key: {key} name: {name} msg: {msg} "
                    dbg_msg += 'method unit changed control'
                    dbg_msg += f" value: {control['value']}"
                    LOGGER.debug(dbg_msg)

                    if key not in self.units:
                        # New unit discovered
                        address = None
                        if 'details' in msg and 'address' in msg['details']:
                            address = msg['details']['address']
                        elif 'address' in msg:
                            address = msg['address']
                        online = False
                        unit_id = msg['id']
                        controls = []

                        if 'online' in msg:
                            online = msg['online']

                        if 'controls' in msg:
                            controls = msg['controls']

                        unit = Unit(
                            name=name,
                            address=address,
                            unit_id=unit_id,
                            online=online,
                            wire_id=self._wire_id,
                            network_id=self._network_id,
                            controller=self._controller,
                            controls=controls
                        )

                        self.units[key] = unit

                    # Update value
                    self.units[key].value = control['value']

                    if 'details' in msg and 'fixture' in msg['details']:
                        self.units[key].fixture = msg['details']['fixture']
                    elif 'fixture' in msg:
                        self.units[key].fixture = msg['fixture']

                    if 'online' in msg:
                        self.units[key].online = msg['online']

                    if 'details' in msg and 'fixture_model' in msg['details']:
                        self.units[key].fixture_model = \
                            msg['details']['fixture_model']
                    elif 'fixture_model' in msg:
                        self.units[key].fixture_model = \
                            msg['fixture_model']

                    if 'details' in msg and 'OEM' in msg['details']:
                        self.units[key].oem = msg['details']['OEM']
                    elif 'OEM' in msg:
                        self.units[key].oem = msg['OEM']

                    if 'details' in msg and 'controls' in msg['details']:
                        self.units[key].controls = msg['details']['controls']
                    elif 'controls' in msg:
                        self.units[key].controls = msg['controls']

                    changes[key] = self.units[key]

        return changes

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
        self._online = online

        for _, unit in self.units.items():
            unit.online = online

    def get_unit(self, *, unit_id: int):
        '''
        Get unit
        '''
        key = f"{self._network_id}-{unit_id}"

        return self.units[key]

    def get_units(self):
        '''
        Getter for all units
        '''
        result = []
        for _, value in self.units.items():
            result.append(value)

        return result

    def get_units_unique_ids(self):
        '''
        Getter for getting all units uniq ids
        '''
        result = []
        for _, value in self.units.items():
            result.append(value.unique_id)

        return result

    async def turn_unit_on(self, *, unit_id: int):
        '''
        Turn unit on
        '''
        key = f"{self._network_id}-{unit_id}"

        await self.units[key].turn_unit_on()

    async def turn_unit_off(self, *, unit_id: int):
        '''
        Turn unit off
        '''
        key = f"{self._network_id}-{unit_id}"

        await self.units[key].turn_unit_off()

    def set_controls(self, *,
                     unit_id: int,
                     data):
        '''
        Setter for unit state
        '''
        key = f"{self._network_id}-{unit_id}"

        self.units[key].controls = data

    def supports_color_temperature(self, *, unit_id: int):
        '''
        Check if unit supports color temperature
        '''
        key = f"{self._network_id}-{unit_id}"
        result = self.units[key].supports_color_temperature()

        return result

    def supports_brightness(self, *, unit_id: int):
        '''
        Check if unit supports brightness temperature
        '''
        key = f"{self._network_id}-{unit_id}"
        result = self.units[key].supports_brightness()

        return result

    def get_supported_color_temperature(self, *, unit_id: int):
        '''
        Get supported color temperatures
        '''
        key = f"{self._network_id}-{unit_id}"
        (min, max, current) = self.units[key].get_supported_color_temperature()

        return (min, max, current)

    async def set_unit_color_temperature(self, *,
                                         unit_id: int,
                                         value: int,
                                         source="TW"):
        '''
        Set unit color temperature
        '''
        key = f"{self._network_id}-{unit_id}"
        await self.units[key].set_unit_color_temperature(value=value,
                                                         source=source)

    def __process_units(self, units):
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
        LOGGER.debug(f"Processing units {pformat(units)}")

        for unit_id in units:
            tmp = units[unit_id]
            key = f"{self._network_id}-{unit_id}"
            unit = Unit(
                name=tmp['name'].strip(),
                address=tmp['address'],
                unit_id=unit_id,
                wire_id=self._wire_id,
                network_id=self._network_id,
                controller=self._controller,
                controls=[]
            )
            self.units[key] = unit


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
        return self._value

    @value.setter
    def value(self, value):
        '''
        Setter for value
        '''
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
            LOGGER.info(f"unit is back online: {self}")
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
                LOGGER.debug(
                    f"Adding following control to controls: {control}")
                key = control['type']
                self._controls[key] = control
        elif isinstance(controls, dict):
            LOGGER.debug(
                f"Adding following control to controls: {controls}")
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
    def value(self):
        '''
        Getter for value
        '''
        return self._value

    @value.setter
    def value(self, value):
        '''
        Setter for value
        '''
        self._value = value

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
            'Colorsource': {'source': source}
        }

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

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

        await self._controller.ws_send_message(message)

    def get_supported_color_temperature(self):
        '''
        Return the supported color temperatures,
        (0, 0, 0) if nothing is supported
        '''
        min = 0
        max = 0
        current = 0

        if not self._controls:
            LOGGER.debug(f"control is None for unit: {self}")
            return (min, max, current)

        if 'CCT' in self._controls and self._controls['CCT']:
            min = self._controls['CCT']['min']
            max = self._controls['CCT']['max']
            current = self._controls['CCT']['value']

        return (min, max, current)

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
        return round(1000000/self._controls['CCT']['max'])

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
        return round(1000000/self._controls['CCT']['min'])

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
        return round(1000000/self._controls['CCT']['value'])

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
            LOGGER.debug(f"controls is None for unit: {self}")
            return False

        if 'CCT' in self._controls and self._controls['CCT']:
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
            LOGGER.debug(f"controls is None for unit: {self}")
            return False

        if 'Dimmer' in self._controls and self._controls['Dimmer']:
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

            result = f"{result} controls={self._controls}"

        result = f"{result} >"

        return result
