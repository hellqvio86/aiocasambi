"""State representation of Casanbi Scene"""
import logging

from pprint import pformat

LOGGER = logging.getLogger(__name__)


SCENE_STATE_OFF = "off"
SCENE_STATE_ON = "on"


"""
'scenes':
 {'1': {'color': '#FFFFFF',
       'hidden': False,
       'icon': 0,
       'id': 1,
       'name': 'Foo',
       'position': 0,
       'type': 'REGULAR',
       'units': {'10': {'id': 10}, '8': {'id': 8}}},
 '2': {'color': '#FFFFFF',
       'hidden': False,
       'icon': 0,
       'id': 2,
       'name': 'Bar',
       'position': 1,
       'type': 'REGULAR',
       'units': {'12': {'id': 12}}},
 '3': {'color': '#FFFFFF',
       'hidden': False,
       'icon': 0,
       'id': 3,
       'name': 'Foobar',
       'position': 2,
       'type': 'REGULAR',
       'units': {'1': {'id': 1}}}}
"""


class Scene:
    """Represents a client network device."""

    def __init__(
        self, *, name, scene_id, network_id, wire_id, controller, state=SCENE_STATE_OFF
    ):
        self._name = name
        self._scene_id = scene_id
        self._network_id = network_id
        self.state = state
        self._wire_id = wire_id
        self._controller = controller

    def __repr__(self) -> str:
        """Return the representation."""
        result = ""
        name = self._name

        scene_id = self._scene_id
        network_id = self._network_id

        state = self.state

        wire_id = self._wire_id

        result += f"<Scene {name}: scene_id={scene_id} "
        result += f"state={state} network_id={network_id} "
        result += f"wire_id={wire_id}>"

        return result

    def set_wire_id(self, *, wire_id: int) -> None:
        """
        Setter for wire_id
        """
        self._wire_id = wire_id

    @property
    def name(self):
        """
        Getter for name
        """
        return self._name


class Scenes:
    """
    Class for representing Casambi Scenes
    """

    def __init__(
        self, scenes: set, *, network_id: int, wire_id: int, controller
    ) -> None:
        """
        Constructor
        """
        self._network_id = network_id
        self._controller = controller
        self._wire_id = wire_id
        self.scenes = {}

        LOGGER.debug(f"Processing scenes {pformat(scenes)}")

        self.__process_scenes(scenes)

        LOGGER.debug(f"Processing scenes {pformat(self.scenes)}")

    def get_scenes(self) -> list:
        """
        Getter for scenes
        """
        result = []
        for _, value in self.scenes.items():
            result.append(value)

        return result

    def set_wire_id(self, *, wire_id: int) -> None:
        """
        Setter for wire_id
        """
        self._wire_id = wire_id

        for _, value in self.scenes.items():
            value.set_wire_id(wire_id=wire_id)

    def __process_scenes(self, scenes: dict) -> None:
        """
        Function for processing units
        Units raw format:
        'scenes':
        {
        '1': {
            'name': 'Foo',
            'id': 1,
            'position': 0,
            'icon': 0,
            'color': '#FFFFFF',
            'type': 'REGULAR',
            'hidden': False,
            'units': {
                '8': {
                    'id': 8,
                    'state': 'fc03'
                    },
                '10': {
                    'id': 10,
                    'state':
                    'fc03'}
                }
            },
        '2': {
            'name': 'Foobar',
            'id': 2,
            'position': 1,
            'icon': 0,
            'color': '#FFFFFF',
            'type': 'REGULAR',
            'hidden': False,
            'units': {
                '12': {
                    'id': 12,
                    'state': 'fc03'}
                }
            },
        '3': {
            'name': 'Master Bathroom',
            'id': 3,
            'position': 2,
            'icon': 0,
            'color': '#FFFFFF',
            'type': 'REGULAR',
            'hidden': False,
            'units': {
                '1': {
                    'id': 1,
                    'state': 'fc03'
                    }
                }
            }
        }
        '''
        """
        LOGGER.debug(f"Processing units {pformat(scenes)}")

        for scene_id in scenes:
            tmp = scenes[scene_id]
            key = f"{self._network_id}-{scene_id}"
            scene = Scene(
                name=tmp["name"].strip(),
                scene_id=scene_id,
                network_id=self._network_id,
                wire_id=self._wire_id,
                controller=self._controller,
            )
            self.scenes[key] = scene
