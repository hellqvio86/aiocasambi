"""State representation of Casanbi Unit"""

import logging

from .errors import AiocasambiException
from pprint import pformat

LOGGER = logging.getLogger(__name__)

UNIT_STATE_OFF = 'off'
UNIT_STATE_ON = 'on'


class Units():
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
        if 'units' not in data:
            # Safe guard
            return

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
        """
        changes = {}
        key = f"{self._network_id}-{msg['id']}"

        LOGGER.debug(f"process_unit_event Processing msg: {msg}")

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
                    LOGGER.debug(f"key: {key} name: {name} msg: {msg} method unit changed control value: {control['value']}")

                    if key not in self.units:
                        # New unit discovered
                        address = None
                        if 'details' in msg and 'address' in msg['details']:
                            address = msg['details']['address']
                        elif 'address' in msg:
                            address = msg['address']
                        online = False
                        unit_id = msg['id']

                        if 'online' in msg:
                            online = msg['online']

                        unit = Unit(
                            name=name,
                            address=address,
                            unit_id=unit_id,
                            online=online,
                            wire_id=self._wire_id,
                            network_id=self._network_id,
                            controller=self._controller
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
                        self.units[key].fixture_model = msg['details']['fixture_model']
                    elif 'fixture_model' in msg:
                        self.units[key].fixture_model = msg['fixture_model']

                    if 'details' in msg and 'OEM' in msg['details']:
                        self.units[key].oem = msg['details']['OEM']
                    elif 'OEM' in msg:
                        self.units[key].oem = msg['OEM']

                    changes[key] = self.units[key]

        return changes

    @property
    def online(self):
        return self._online

    @online.setter
    def online(self, online):
        self._online = online

        for _, unit in self.units.items():
            unit.online = online

    def get_units(self):
        result = []
        for _, value in self.units.items():
            result.append(value)

        return result

    def get_units_unique_ids(self):
        result = []
        for _, value in self.units.items():
            result.append(value.unique_id)

        return result

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
                controller=self._controller
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
        value=0,
        online=True,
        state=UNIT_STATE_OFF):
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

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
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
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def fixture_model(self):
        return self._fixture_model

    @fixture_model.setter
    def fixture_model(self, fixture_model):
        self._fixture_model = fixture_model

    @property
    def online(self):
        return self._online

    @online.setter
    def online(self, online):
        if not self._online and online:
            LOGGER.info(f"unit is back online: {self}")
        self._online = online

    @property
    def oem(self):
        return self._oem

    @oem.setter
    def oem(self, oem):
        self._oem = oem

    @property
    def fixture(self):
        return self._fixture

    @fixture.setter
    def fixture(self, fixture):
        self._fixture = fixture

    @property
    def unique_id(self):
        return f"{self._network_id}-{self._unit_id}"

    @property
    def controller(self):
        return self._controller

    @controller.setter
    def controller(self, controller):
        self._controller = controller

    async def turn_unit_off(self):
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
            reason += "got: {}".format(unit_id)
            raise AiocasambiException(reason)

        target_controls = {'Dimmer': {'value': 1}}

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        await self._controller.ws_send_message(message)

    async def set_unit_value(self, *, value):
        '''
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

        await self._controller.ws_send_message(message)

    def __repr__(self) -> str:
        """Return the representation."""
        name = self._name

        address = self._address

        unit_id = self._unit_id
        network_id = self._network_id

        value = self._value
        state = self._state

        wire_id = self._wire_id

        result = f"<Unit {name}: unit_id={unit_id} address={address} value={value} state={state} online={self._online} network_id={network_id} wire_id={wire_id}"

        if self._fixture:
            result = f"{result} fixure={self._fixture}"

        if self._fixture_model:
            result = f"{result} fixture_model={self._fixture_model}"

        if self._oem:
            result = f"{result} oem={self._oem}"

        result = f"{result} >"

        return result
