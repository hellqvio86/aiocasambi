"""State representation of Casanbi Unit"""

import logging
import json

from .errors import AiocasambiException
from pprint import pformat

LOGGER = logging.getLogger(__name__)

UNIT_STATE_OFF = 'off'
UNIT_STATE_ON = 'on'

class Units():
    def __init__(self, units: set, *, network_id, wire_id, web_sock) -> None:
        self._network_id = network_id
        self._wire_id = wire_id
        self._web_sock = web_sock
        self.units = {}

        self.__process_units(units)

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

        LOGGER.debug(f"Processing msg: {msg}")

        if 'online' in msg and msg['online'] == False:
            LOGGER.debug(f"Gateway is not online msg{msg}")

        if 'method' in msg and msg['method'] == 'unitChanged':
            controls = msg['controls']
            for control in controls:
                LOGGER.debug(f"method unit changed control: {control}")
                if 'type' in control and control['type'] == 'Dimmer':
                    name = (msg['details']['name']).strip()
                    LOGGER.debug(f"key: {key} name: {name} method unit changed control value: {control['value']}")

                    if key not in self.units:
                        # New unit discovered
                        #name = (msg['details']['name']).strip()
                        address = msg['details']['address']
                        online = False
                        unit_id = msg['id']

                        if 'online' in msg:
                            online = msg['online']

                        unit = Unit(
                            name= name,
                            address = address,
                            unit_id = unit_id,
                            online = online,
                            wire_id = self._wire_id,
                            network_id = self._network_id,
                            web_sock = self._web_sock
                            )
                        self.units[key] = unit

                    # Update value
                    self.units[key].value = control['value']

                    if 'fixture' in msg['details']:
                        self.units[key].fixture = msg['details']['fixture']

                    if 'online' in msg:
                        self.units[key].online = msg['online']

                    if 'fixture_model' in msg['details']:
                        self.units[key].fixture_model = msg['details']['fixture_model']

                    if 'OEM' in msg['details']:
                        self.units[key].oem = msg['details']['OEM']

                    changes[key] = self.units[key]
        
        return changes


    def get_units(self):
        result = []
        for _, value in self.units.items():
            result.append(value)

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
                name= tmp['name'].strip(),
                address = tmp['address'],
                unit_id = unit_id,
                wire_id = self._wire_id,
                network_id = self._network_id,
                web_sock = self._web_sock
                )
            self.units[key] = unit


class Unit():
    """Represents a client network device."""
    def __init__(self, *, name, address, unit_id, network_id, wire_id, web_sock, value=0, online=True, state=UNIT_STATE_OFF):
        self._name = name
        self._address = address
        self._unit_id = unit_id
        self._network_id = network_id
        self._value = value
        self._state = state
        self._fixture_model = None
        self._fixture = None
        self._wire_id = wire_id
        self._web_sock = web_sock
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
    def websocket(self):
        return self._web_sock

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

        if not self._web_sock:
            raise AiocasambiException('No websocket connection!')

        target_controls = {'Dimmer': {'value': 0}}

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        await self._web_sock.send_messge(message)

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

        if not self._web_sock:
            raise AiocasambiException('No websocket connection!')

        target_controls = {'Dimmer': {'value': 1}}

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        await self._web_sock.send_messge(message)

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

        if not self._web_sock:
            raise AiocasambiException('No websocket connection!')

        target_controls = {'Dimmer': {'value': value}}

        message = {
            "wire": self._wire_id,
            "method": 'controlUnit',
            "id": unit_id,
            "targetControls": target_controls
        }

        await self._web_sock.send_messge(message)


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
        
        if self._web_sock:
            result = f"{result} websocket={self._web_sock}"

        result = f"{result} >"

        return result
