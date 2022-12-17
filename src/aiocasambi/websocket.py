"""
Websocket implementation of Casambi cloud api
"""
import asyncio
import json
import logging
import uuid

import aiohttp

from .consts import (
    SIGNAL_CONNECTION_STATE,
    SIGNAL_DATA,
    STATE_RUNNING,
    STATE_DISCONNECTED,
    STATE_STARTING,
    STATE_STOPPED,
    CASAMBI_REASONS_BY_STATUS_CODE,
)

LOGGER = logging.getLogger(__name__)


class WSClient:
    """
    Web Socket Client
    """

    def __init__(
        self,
        *,
        session,
        ssl_context,
        api_key,
        network_id,
        session_id,
        callback,
        controller,
        wire_id=3,
        network_timeout=30,
    ):
        """
        Constructor for Web Socket Client
        """
        self.api_key = api_key
        self.network_id = network_id
        self.session_id = session_id
        self.network_timeout = network_timeout

        self.session = session
        self.ssl_context = ssl_context
        self.session_handler_callback = callback

        self.url = "wss://door.casambi.com/v1/bridge/"

        self._loop = asyncio.get_running_loop()

        self.web_sock = None
        self._controller = controller
        self.wire_id = wire_id

        self._data = None
        self._state = STATE_DISCONNECTED

    def __repr__(self) -> str:
        """Return the representation."""
        result = f"<WSClient state={self._state} wire_id={self.wire_id}>"

        return result

    @property
    def data(self) -> dict:
        """Get data"""
        return self._data

    def get_state(self) -> str:
        """Get state"""
        return self._state

    @property
    def state(self) -> str:
        """Get state"""
        return self._state

    @state.setter
    def state(self, state_value) -> None:
        """Setter for state"""
        LOGGER.debug("websocket.state %s", state_value)

        self._state = state_value
        self.session_handler_callback(SIGNAL_CONNECTION_STATE, self.wire_id)

    def start(self) -> None:
        """Start the websocket connection"""
        LOGGER.debug(f"websocket.start state {self.state}")

        if self.state != STATE_RUNNING:
            self.state = STATE_STARTING
            self._loop.create_task(self.running())

    def stop(self) -> None:
        """
        Close websocket connection.
        """
        self.state = STATE_STOPPED

    async def ws_open(self) -> None:
        """
        Send open message to Casambi Cloud api
        """
        reference = f"{uuid.uuid1()}"

        message = {
            "method": "open",
            "id": self.network_id,
            "session": self.session_id,
            "ref": reference,
            "wire": self.wire_id,  # wire id
            "type": 1,  # Client type, use value 1 (FRONTEND)
        }

        LOGGER.debug(f"ws_open message: {message}")

        await self.web_sock.send_str(json.dumps(message))

    async def send_message(self, message: dict) -> bool:
        """
        Send websocket message
        """
        success = False
        LOGGER.debug(f"send_message message {message}")

        if not self.web_sock:
            # Websocket is none
            LOGGER.error("websocket.send_message: websocket is None")
            self.state = STATE_DISCONNECTED

            return success

        try:
            await self.web_sock.send_str(json.dumps(message))
            success = True
        except ConnectionError as err:
            error_msg = "websocket caught ConnectionError in"
            error_msg += f"websocket.send_message {err}"

            LOGGER.error(error_msg)

            self.state = STATE_DISCONNECTED
        except AttributeError as err:
            error_msg = "websocket caught AttributeError in"
            error_msg += f"websocket.send_message {err}"

            LOGGER.error(error_msg)

            self.state = STATE_DISCONNECTED
        return success

    async def ws_loop(self) -> None:
        """
        Main websocket loop
        """
        LOGGER.debug("Starting ws_loop")

        web_sock = await self.session.ws_connect(
            self.url, ssl=self.ssl_context, heartbeat=15, protocols=(self.api_key,)
        )

        self.state = STATE_RUNNING

        self.web_sock = web_sock

        await self.ws_open()

        async for msg in self.web_sock:
            dbg_msg = "websocket running: "
            dbg_msg += f"wire_id: {self.wire_id} "
            dbg_msg += f"msg: {msg}"

            LOGGER.debug(dbg_msg)

            if self.state == STATE_STOPPED:
                LOGGER.debug("websocket running STATE_STOPPED")
                break

            if msg.type == aiohttp.WSMsgType.TEXT:
                self._data = json.loads(msg.data)
                self.session_handler_callback(SIGNAL_DATA, self.wire_id)

                dbg_msg = "websocket recived "
                dbg_msg += "msg.type: aiohttp.WSMsgType.TEXT "
                dbg_msg += f"data: {self._data}"

                LOGGER.debug(dbg_msg)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                self._data = json.loads(msg.data)
                self.session_handler_callback(SIGNAL_DATA, self.wire_id)

                dbg_msg = "websocket recived "
                dbg_msg += "msg.type: aiohttp.WSMsgType.BINARY "
                dbg_msg += f"data: {self._data}"

                LOGGER.debug(dbg_msg)
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                warning_msg = "websocket recived "
                warning_msg += "aiohttp.WSMsgType.CLOSED "
                warning_msg += "websocket connection closed"

                LOGGER.warning(warning_msg)

                break

            elif msg.type == aiohttp.WSMsgType.ERROR:
                LOGGER.error("websocket recived AIOHTTP websocket error")
                break

    async def running(self) -> None:
        """
        Start websocket connection.
        """
        while True:
            LOGGER.debug("websocket opening session")
            try:
                await self.ws_loop()

            except ConnectionResetError as err:
                if self.state != STATE_STOPPED:
                    err_msg = "websocket caught ConnectionResetError, "
                    err_msg += f"err: {err}"
                    LOGGER.error(err_msg)

                    self.state = STATE_DISCONNECTED
            except ConnectionError as err:
                if self.state != STATE_STOPPED:
                    err_msg = f"websocket caught ConnectionError, err: {err}"
                    LOGGER.error(err_msg)

                    self.state = STATE_DISCONNECTED
            except aiohttp.ClientConnectorError as err:
                if self.state != STATE_STOPPED:
                    err_msg = "websocket caught aiohttp.ClientConnectorError"

                    if hasattr(err, "status"):
                        err_msg += f' status: "{err.status}"'
                        if err.status in CASAMBI_REASONS_BY_STATUS_CODE:
                            reason = CASAMBI_REASONS_BY_STATUS_CODE[err.status]
                            err_msg += f' reason: "{reason}"'
                        else:
                            if hasattr(err, "message"):
                                err_msg += f' message: "{err.message}"'
                    LOGGER.error(err_msg)

                    self.state = STATE_DISCONNECTED
            except aiohttp.WSServerHandshakeError as err:
                if self.state != STATE_STOPPED:
                    err_msg = "websocket caught aiohttp.WSServerHandshakeError,"
                    if hasattr(err, "status"):
                        err_msg += f' status: "{err.status}"'

                        if err.status in CASAMBI_REASONS_BY_STATUS_CODE:
                            reason = CASAMBI_REASONS_BY_STATUS_CODE[err.status]
                            err_msg += f' reason: "{reason}"'
                        else:
                            if hasattr(err, "message"):
                                err_msg += f' message: "{err.message}"'
                    LOGGER.error(err_msg)

                    self.state = STATE_DISCONNECTED
            except Exception as err:
                if self.state != STATE_STOPPED:
                    error_msg = f"websocket: Unexpected Exception: < {err} "
                    error_msg += f'type="{type(err)}">'

                    LOGGER.error(error_msg)
                    LOGGER.exception("An unknown exception was thrown!")

                    self.state = STATE_DISCONNECTED

                    raise err
            await asyncio.sleep(self.network_timeout)
