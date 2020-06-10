import asyncio
import json
import logging
import uuid

import aiohttp

LOGGER = logging.getLogger(__name__)

SIGNAL_DATA = "data"
SIGNAL_CONNECTION_STATE = "state"

STATE_DISCONNECTED = "disconnected"
STATE_RUNNING = "running"
STATE_STARTING = "starting"
STATE_STOPPED = "stopped"

class WSClient():
    def __init__(self, *, session, ssl_context, api_key, network_id, user_session_id, callback, wire_id=3):
        self.api_key = api_key
        self.network_id = network_id
        self.user_session_id = user_session_id

        self.session = session
        self.ssl_context = ssl_context
        self.session_handler_callback = callback

        self.url = "wss://door.casambi.com/v1/bridge/"

        self._loop = asyncio.get_running_loop()

        self.web_sock = None
        self.wire_id = wire_id

        self._data = None
        self._state = None

    def __repr__(self) -> str:
        """Return the representation."""
        result = f"<WSClient state={self._state} wire_id={self.wire_id}>"

        return result

    @property
    def data(self):
        """Get data"""
        return self._data

    @property
    def state(self):
        """Get state"""
        return self._state

    @state.setter
    def state(self, state_value):
        """"""
        LOGGER.debug("websocket.state %s", state_value)

        self._state = state_value
        self.session_handler_callback(SIGNAL_CONNECTION_STATE)

    def start(self):
        LOGGER.debug(f"websocket.start state {self.state}")

        if self.state != STATE_RUNNING:
            self.state = STATE_STARTING
            self._loop.create_task(self.running())

    def stop(self):
        """Close websocket connection."""
        self.state = STATE_STOPPED

    async def ws_open(self):
        reference = "{}".format(uuid.uuid1())

        message = {
            "method": "open",
            "id": self.network_id,
            "session": self.user_session_id,
            "ref": reference,
            "wire": self.wire_id,  # wire id
            "type": 1  # Client type, use value 1 (FRONTEND)
        }

        await self.web_sock.send_str(json.dumps(message))

    async def send_messge(self, message):
        LOGGER.debug(f"send_messge message {message}")
        await self.web_sock.send_str(json.dumps(message))

    async def running(self):
        """Start websocket connection."""
        try:
            async with self.session.ws_connect(
                self.url, ssl=self.ssl_context, heartbeat=15, protocols=(self.api_key,)
            ) as web_sock:
                self.state = STATE_RUNNING

                self.web_sock = web_sock

                await self.ws_open()

                async for msg in self.web_sock:
                    LOGGER.debug(f"websocket running: wire_id: {self.wire_id} msg: {msg}")

                    if self.state == STATE_STOPPED:
                        LOGGER.debug(f"websocket running STATE_STOPPED")
                        break

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self._data = json.loads(msg.data)
                        self.session_handler_callback(SIGNAL_DATA)
                        LOGGER.debug(f"websocket msg.type: {msg.type} data: {self._data}")
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        self._data = json.loads(msg.data)
                        self.session_handler_callback(SIGNAL_DATA)
                        LOGGER.debug(f"websocket msg.type {msg.type} data: {self._data}")
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        LOGGER.warning("websocket AIOHTTP websocket connection closed")
                        break

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        LOGGER.error("websocket AIOHTTP websocket error")
                        break

        except aiohttp.ClientConnectorError:
            if self.state != STATE_STOPPED:
                LOGGER.error("websocket: Client connection error")
                self.state = STATE_DISCONNECTED

        except Exception as err:
            if self.state != STATE_STOPPED:
                LOGGER.error(f"websocket: Unexpected error {err}")
                self.state = STATE_DISCONNECTED

        else:
            if self.state != STATE_STOPPED:
                LOGGER.debug(f"websocket setting state to STATE_DISCONNECED")
                self.state = STATE_DISCONNECTED
