"""Comprehensive unit tests for aiocasambi."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from aiocasambi import Controller
from aiocasambi.consts import (
    CASAMBI_FIXTURE_IDS,
    CASAMBI_REASONS_BY_STATUS_CODE,
    SIGNAL_CONNECTION_STATE,
    SIGNAL_DATA,
    STATE_DISCONNECTED,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
)
from aiocasambi.errors import (
    AiocasambiException,
    ApiNotEnabled,
    BadRequest,
    CasambiAPIServerError,
    InvalidSession,
    MethodNotAllowed,
    QoutaLimitsExceeded,
    RequestedDataNotFound,
    RetrievalIntervalIsTooLong,
    Unauthorized,
    get_error,
)
from aiocasambi.helper import Helper, merge_result
from aiocasambi.scenes import SCENE_STATE_OFF, Scene, Scenes
from aiocasambi.unit import UNIT_STATE_OFF, UNIT_STATE_ON, Unit
from aiocasambi.units import Units
from aiocasambi.websocket import WSClient


class FakeContextManager:
    """Async context manager wrapper for mocked aiohttp responses."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_aio_response(status=200, json_data=None, text="OK", content_type="application/json"):
    res = MagicMock()
    res.status = status
    res.content_type = content_type
    res.json = AsyncMock(return_value=json_data if json_data is not None else {})
    res.text = AsyncMock(return_value=text)
    return FakeContextManager(res)


def test_errors_and_consts():
    assert get_error(400) is BadRequest
    assert get_error(401) is Unauthorized
    assert get_error(403) is ApiNotEnabled
    assert get_error(404) is RequestedDataNotFound
    assert get_error(405) is MethodNotAllowed
    assert get_error(410) is InvalidSession
    assert get_error(416) is RetrievalIntervalIsTooLong
    assert get_error(429) is QoutaLimitsExceeded
    assert get_error(500) is CasambiAPIServerError
    assert get_error(999) is AiocasambiException
    assert 200 in CASAMBI_REASONS_BY_STATUS_CODE
    assert 2516 in CASAMBI_FIXTURE_IDS


def test_merge_result():
    src = {"a": {"b": 1, "c": 2}, "d": 3}
    dst = {"a": {"b": 0, "e": 4}}
    merged = merge_result(src, dst)
    assert merged == {"a": {"b": 1, "c": 2, "e": 4}, "d": 3}


@pytest.mark.asyncio
async def test_helper():
    session = MagicMock()
    helper = Helper(email="user@example.com", api_key="key", websession=session)

    # request success
    session.request.return_value = _make_aio_response(200, {"sessionId": "s1"})
    assert await helper.test_user_password(password="pw") is True
    assert await helper.test_network_password(password="pw") is True

    # request empty json -> False
    session.request.return_value = _make_aio_response(200, {})
    assert await helper.test_user_password(password="pw") is False
    assert await helper.test_network_password(password="pw") is False

    # Unauthorized -> False
    session.request.return_value = _make_aio_response(401, text="unauth")
    assert await helper.test_user_password(password="pw") is False
    assert await helper.test_network_password(password="pw") is False

    # ClientConnectorError retry then success
    conn_err = aiohttp.client_exceptions.ClientConnectorError(MagicMock(), OSError("fail"))
    with patch("aiocasambi.helper.asyncio.sleep", new_callable=AsyncMock):
        with patch.object(helper, "request", side_effect=[conn_err, {"ok": True}]):
            assert await helper.test_user_password(password="pw") is True
        with patch.object(helper, "request", side_effect=[conn_err, {"ok": True}]):
            assert await helper.test_network_password(password="pw") is True

    # ClientError propagation in request
    session.request.side_effect = aiohttp.client_exceptions.ClientError("boom")
    with pytest.raises(aiohttp.client_exceptions.ClientError):
        await helper.request("get", url="https://door.casambi.com/v1/test")


def test_scenes():
    ctrl = MagicMock()
    raw_scenes = {
        "1": {"name": " Cozy Evening ", "id": 1},
        "2": {"name": "Morning", "id": 2},
    }
    scenes = Scenes(raw_scenes, network_id="net1", wire_id=1, controller=ctrl)
    scene_list = scenes.get_scenes()
    assert len(scene_list) == 2
    s1 = scenes.scenes["net1-1"]
    assert s1.name == "Cozy Evening"
    assert s1.state == SCENE_STATE_OFF
    assert "Scene Cozy Evening" in repr(s1)

    scenes.set_wire_id(wire_id=5)
    assert s1._wire_id == 5


@pytest.mark.asyncio
async def test_unit_properties_and_methods():
    ctrl = MagicMock()
    ctrl.ws_send_message = AsyncMock()
    ctrl.get_websocket_state.return_value = STATE_RUNNING

    controls_list = [
        {"type": "Dimmer", "value": 0.5},
        {"type": "Vertical", "value": 0.25},
        {"type": "CCT", "min": 2200, "max": 6000, "value": 4000},
        {"type": "Color", "rgb": "rgb(100, 150, 200)"},
        {"type": "White", "value": 0.5},
    ]
    unit = Unit(
        name=" Ceiling Lamp ",
        address="aabbccddeeff",
        type="Luminaire",
        unit_id=7,
        network_id="net1",
        wire_id=2,
        controller=ctrl,
        controls=controls_list,
        fixture_id=4027,
    )

    assert unit.name == "Ceiling Lamp"
    unit.name = " Desk Lamp "
    assert unit.name == "Desk Lamp"
    assert unit.unit_id == 7
    assert unit.network_id == "net1"
    assert unit.address == "aabbccddeeff"
    assert unit.unique_id == "net1-aabbccddeeff"
    unit._address = None
    assert unit.unique_id == "net1-7"
    unit._address = "aabbccddeeff"

    assert unit.value == 0.5
    unit.value = 0
    assert unit.state == UNIT_STATE_OFF
    unit.value = 0.8
    assert unit.state == UNIT_STATE_ON
    with pytest.raises(AiocasambiException):
        unit.value = 1.5

    assert unit.distribution == 0.25
    unit.distribution = 0.75
    with pytest.raises(AiocasambiException):
        unit.distribution = -0.1

    unit.type = "Driver"
    assert unit.type == "Driver"
    assert unit.is_light() is True
    unit.type = "BatterySwitch"
    assert unit.is_light() is False
    unit.type = "Sensor"
    assert unit.is_light() is False
    unit.type = "Luminaire"
    assert unit.is_light() is True

    unit.fixture_model = "ModelX"
    assert unit.fixture_model == "ModelX"
    unit.fixture_id = 1234
    assert unit.fixture_id == 1234
    unit.firmware_version = "26.24"
    assert unit.firmware_version == "26.24"
    unit.oem = "Vadsbo"
    assert unit.oem == "Vadsbo"
    unit.fixture = "Fix1"
    assert unit.fixture == "Fix1"
    unit.enabled = False
    assert unit.enabled is False
    unit.state = UNIT_STATE_OFF
    assert unit.state == UNIT_STATE_OFF
    unit.controller = ctrl
    assert unit.controller is ctrl

    assert unit.online is True
    unit.online = False
    assert unit.online is False
    unit.online = True
    ctrl.get_websocket_state.return_value = STATE_DISCONNECTED
    assert unit.online is False
    ctrl.get_websocket_state.return_value = STATE_RUNNING

    # controls setter with nested list and dict
    unit.controls = [[{"type": "Dimmer", "value": 0.9}]]
    assert unit.controls["Dimmer"]["value"] == 0.9

    # Capabilities and color getters
    assert unit.supports_rgbw() is True
    assert unit.supports_rgb() is True
    assert unit.supports_color_temperature() is True
    assert unit.supports_brightness() is True
    assert unit.supports_distribution() is True
    assert unit.get_supported_color_temperature() == (2200, 6000, 4000)
    assert unit.get_max_mired() == round(1000000 / 2200)
    assert unit.get_min_mired() == round(1000000 / 6000)
    assert unit.get_color_temp() == round(1000000 / 4000)
    assert unit.get_rgb_color() == (100, 150, 200)
    assert unit.get_rgbw_color() == (100, 150, 200, 128)

    # Invalid rgb string
    unit._controls["Color"]["rgb"] = "invalid"
    assert unit.get_rgb_color() == (0, 0, 0)

    assert "Unit Desk Lamp" in repr(unit)

    # Async unit control actions (and unit_id type conversions)
    for uid in (7, "7", 7.0):
        unit._unit_id = uid
        await unit.turn_unit_off()
        await unit.turn_unit_on()
        await unit.set_unit_rgbw(color_value=(10, 20, 30, 40))
        await unit.set_unit_rgb(color_value=(10, 20, 30), send_rgb_format=False)
        await unit.set_unit_rgb(color_value=(10, 20, 30), send_rgb_format=True)
        await unit.set_unit_color_temperature(value=333, source="mired")
        await unit.set_unit_color_temperature(value=1500)  # min clamp
        await unit.set_unit_color_temperature(value=7000)  # max clamp
        await unit.set_unit_value(value=0.5)
        await unit.set_unit_distribution(distribution=0.5)
        await unit.set_unit_target_controls(
            target_controls={"Dimmer": {"value": 0.6}, "Vertical": {"value": 0.4}}
        )

    with pytest.raises(AiocasambiException):
        await unit.set_unit_value(value=2.0)
    with pytest.raises(AiocasambiException):
        await unit.set_unit_distribution(distribution=2.0)

    # Invalid unit_id type
    unit._unit_id = [7]
    for coro_fn in (
        lambda: unit.turn_unit_off(),
        lambda: unit.turn_unit_on(),
        lambda: unit.set_unit_rgbw(color_value=(1, 2, 3, 4)),
        lambda: unit.set_unit_rgb(color_value=(1, 2, 3)),
        lambda: unit.set_unit_color_temperature(value=3000),
        lambda: unit.set_unit_value(value=0.5),
        lambda: unit.set_unit_distribution(distribution=0.5),
        lambda: unit.set_unit_target_controls(target_controls={}),
    ):
        with pytest.raises(AiocasambiException):
            await coro_fn()

    # Empty controls branches
    unit._unit_id = 7
    unit._controls = {}
    assert unit.value == 0
    assert unit.distribution == 0
    assert unit.supports_rgbw() is False
    assert unit.supports_rgb() is False
    assert unit.supports_color_temperature() is False
    assert unit.supports_brightness() is False
    assert unit.supports_distribution() is False
    unit.get_supported_color_temperature()


@pytest.mark.asyncio
async def test_units_collection():
    ctrl = MagicMock()
    ctrl.ws_send_message = AsyncMock()
    ctrl.get_websocket_state.return_value = STATE_RUNNING
    ctrl.get_fixture_information = AsyncMock(
        return_value={"type": "Driver", "vendor": "VendorA", "model": "ModelA"}
    )

    raw_units = {
        "1": {
            "name": " Hall ",
            "address": "112233445566",
            "type": "Luminaire",
            "fixtureId": 2516,
        },
        "2": {
            "name": "Kitchen",
            "address": "aabbccddeeff",
            "fixtureId": 99999,
        },
    }
    units = Units(raw_units, network_id="net1", wire_id=1, controller=ctrl)
    assert len(units.get_units()) == 2
    assert len(units.get_units_unique_ids()) == 2
    assert units.get_unit(unit_id=1).name == "Hall"
    assert units.get_unit_from_mac_address(mac_address="112233445566").unit_id == 1
    assert units.get_unit_from_mac_address(mac_address="000000000000") is None
    assert units.get_unit_id_from_mac_address(mac_address="112233445566") == 1
    assert units.get_unit_id_from_mac_address(mac_address="000000000000") is None

    # handle_peer_changed & online property
    changes = units.handle_peer_changed({"online": False})
    assert units.online is False
    assert len(changes) == 2

    # process_network_state
    units.process_network_state({})  # no 'units' key
    with pytest.raises(TypeError):
        units.process_network_state(None)

    net_state = {
        "units": {
            "1": {
                "online": True,
                "name": "Hall Updated",
                "firmwareVersion": "30.0",
                "controls": [
                    [
                        {"type": "Dimmer", "value": 0.7},
                        {"type": "Vertical", "value": 0.3},
                        {"type": "CCT", "min": 2200, "max": 6000, "value": 3500},
                        {"type": "Color", "rgb": "rgb(1, 2, 3)"},
                        {"type": "White", "value": 0.2},
                    ]
                ],
                "OEM": "Vadsbo",
                "fixture_model": "LD220",
            },
            "2": {
                "online": False,
                "name": "Kitchen",
                "details": {"OEM": "Tridonic", "fixture_model": "bDW"},
            },
        }
    }
    units.process_network_state(net_state)
    assert units.get_unit_value(unit_id=1) == 0.7
    assert units.get_unit_distribution(unit_id=1) == 0.3
    assert units.supports_rgbw(unit_id=1) is True
    assert units.supports_rgb(unit_id=1) is True
    assert units.supports_color_temperature(unit_id=1) is True
    assert units.supports_brightness(unit_id=1) is True
    assert units.supports_distribution(unit_id=1) is True
    assert units.get_supported_color_temperature(unit_id=1) == (2200, 6000, 3500)

    # process_unit_event (missing id, existing unit, and newly discovered unit)
    assert units.process_unit_event({"method": "unitChanged"}) is None

    ev1 = {
        "id": 1,
        "method": "unitChanged",
        "online": False,
        "details": {
            "name": "Hall Event",
            "fixture": 2516,
            "fixture_model": "M1",
            "OEM": "O1",
            "controls": [{"type": "Dimmer", "value": 0.4}],
        },
        "controls": [
            {"type": "Dimmer", "value": 0.4},
            {"type": "Vertical", "value": 0.6},
        ],
    }
    res1 = units.process_unit_event(ev1)
    assert "net1-1" in res1

    ev_new = {
        "id": 99,
        "method": "unitChanged",
        "name": "New Unit",
        "address": "ffeeddccbbaa",
        "type": "Luminaire",
        "online": True,
        "fixtureId": 100,
        "fixture": 100,
        "fixture_model": "M2",
        "OEM": "O2",
        "controls": [{"type": "Dimmer", "value": 1.0}],
    }
    res_new = units.process_unit_event(ev_new)
    assert "net1-99" in res_new

    await units.get_fixture_information_for_all_units()
    await units.turn_unit_on(unit_id=1)
    await units.turn_unit_off(unit_id=1)
    units.set_wire_id(wire_id=9)
    units.set_controls(unit_id=1, data={"type": "Dimmer", "value": 0.2})
    await units.set_unit_rgbw(unit_id=1, color_value=(1, 2, 3, 4))
    await units.set_unit_rgb(unit_id=1, color_value=(1, 2, 3))
    await units.set_unit_color_temperature(unit_id=1, value=3000)


@pytest.mark.asyncio
async def test_websocket_client():
    session = MagicMock()
    callback = MagicMock()
    ctrl = MagicMock()

    ws = WSClient(
        session=session,
        ssl_context=None,
        api_key="key",
        network_id="net1",
        session_id="sess1",
        callback=callback,
        controller=ctrl,
        wire_id=3,
        network_timeout=0,
    )

    assert "WSClient" in repr(ws)
    assert ws.get_state() == STATE_DISCONNECTED
    assert ws.data is None

    # send_message when web_sock is None
    assert await ws.send_message({"method": "ping"}) is False

    mock_sock = MagicMock()
    mock_sock.send_str = AsyncMock()
    ws.web_sock = mock_sock
    assert await ws.send_message({"method": "ping"}) is True

    mock_sock.send_str.side_effect = ConnectionError("closed")
    assert await ws.send_message({"method": "ping"}) is False
    mock_sock.send_str.side_effect = AttributeError("no attr")
    assert await ws.send_message({"method": "ping"}) is False

    # ws_loop message types
    msg_text = MagicMock(type=aiohttp.WSMsgType.TEXT, data=json.dumps({"a": 1}))
    msg_bin = MagicMock(type=aiohttp.WSMsgType.BINARY, data=json.dumps({"b": 2}))
    msg_closed = MagicMock(type=aiohttp.WSMsgType.CLOSED)

    class AsyncIterSock:
        def __init__(self, items):
            self._items = list(items)
            self.send_str = AsyncMock()

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._items:
                raise StopAsyncIteration
            return self._items.pop(0)

    session.ws_connect = AsyncMock(return_value=AsyncIterSock([msg_text, msg_bin, msg_closed]))
    await ws.ws_loop()
    assert ws.data == {"b": 2}

    # ws_loop ERROR and STATE_STOPPED
    msg_err = MagicMock(type=aiohttp.WSMsgType.ERROR)
    session.ws_connect = AsyncMock(return_value=AsyncIterSock([msg_err]))
    await ws.ws_loop()

    ws_stopped = AsyncIterSock([msg_text])
    session.ws_connect = AsyncMock(return_value=ws_stopped)
    orig_ws_open = ws.ws_open

    async def stop_after_open():
        await orig_ws_open()
        ws.stop()

    with patch.object(ws, "ws_open", side_effect=stop_after_open):
        await ws.ws_loop()

    # running() error handling
    conn_err_401 = aiohttp.ClientConnectorError(MagicMock(), OSError("fail"))
    conn_err_401.status = 401
    hs_err_410 = aiohttp.WSServerHandshakeError(MagicMock(), (), status=410, message="invalid")

    with (
        patch.object(
            ws,
            "ws_loop",
            side_effect=[
                ConnectionResetError("reset"),
                ConnectionError("conn"),
                conn_err_401,
                hs_err_410,
                RuntimeError("unexpected"),
            ],
        ),
        patch("aiocasambi.websocket.asyncio.sleep", new_callable=AsyncMock),
    ):
        ws._state = STATE_RUNNING
        with pytest.raises(RuntimeError):
            await ws.running()


@pytest.mark.asyncio
async def test_controller_lifecycle():
    session = MagicMock()
    cb = MagicMock()
    ctrl = Controller(
        email="user@example.com",
        api_key="key",
        websession=session,
        user_password="upw",
        network_password="npw",
        callback=cb,
        network_timeout=0,
    )

    # request method
    session.request.return_value = _make_aio_response(200, {"ok": 1})
    assert await ctrl.request("get", url="https://door.casambi.com/v1/test") == {"ok": 1}

    session.request.return_value = _make_aio_response(401, text="unauth")
    with pytest.raises(Unauthorized):
        await ctrl.request("get", url="https://door.casambi.com/v1/test")

    # create_user_session and create_network_session
    user_session_resp = {
        "sessionId": "usess-1",
        "networks": {"net1": {"id": "net1", "sessionId": "nsess-1"}},
    }
    net_session_resp = {
        "net1": {"id": "net1", "sessionId": "nsess-1"},
    }
    with patch.object(ctrl, "request", new=AsyncMock(return_value=user_session_resp)):
        await ctrl.create_session()
        assert "net1" in ctrl._network_ids

    ctrl.user_password = None
    with patch.object(ctrl, "request", new=AsyncMock(return_value=net_session_resp)):
        await ctrl.create_session()

    # initialize + get_network_information + get_network_state + init_unit_state_controls
    net_info_resp = {
        "units": {
            "1": {
                "id": 1,
                "name": "Lamp 1",
                "address": "112233445566",
                "type": "Luminaire",
                "fixtureId": 2516,
            }
        },
        "scenes": {"1": {"id": 1, "name": "Scene 1"}},
    }
    net_state_resp = {
        "units": {
            "1": {
                "id": 1,
                "name": "Lamp 1",
                "online": True,
                "controls": [
                    [
                        {"type": "Dimmer", "value": 0.5},
                        {"type": "CCT", "min": 2200, "max": 6000, "value": 4000},
                        {"type": "Color", "rgb": "rgb(10, 20, 30)"},
                        {"type": "White", "value": 0.5},
                        {"type": "Vertical", "value": 0.5},
                    ]
                ],
            }
        }
    }
    unit_state_resp = {
        "controls": [
            {"type": "Dimmer", "value": 0.5},
            {"type": "CCT", "min": 2200, "max": 6000, "value": 4000},
            {"type": "Color", "rgb": "rgb(10, 20, 30)"},
            {"type": "White", "value": 0.5},
            {"type": "Vertical", "value": 0.5},
        ]
    }

    async def fake_request(method, url=None, **kwargs):
        if url.endswith("/networks/net1"):
            return net_info_resp
        if url.endswith("/networks/net1/state"):
            return net_state_resp
        if url.endswith("/units/1/state"):
            return unit_state_resp
        if "/fixtures/" in url:
            return {"type": "Luminaire", "vendor": "Vadsbo", "model": "LD220"}
        return {}

    with patch.object(ctrl, "request", side_effect=fake_request):
        await ctrl.initialize()

    assert len(ctrl.get_units()) == 1
    assert len(ctrl.get_scenes()) == 1
    assert ctrl.get_unit(unit_id=1, network_id="net1").name == "Lamp 1"
    assert ctrl.get_unit_value(unit_id=1, network_id="net1") == 0.5
    assert ctrl.get_unit_distribution(unit_id=1, network_id="net1") == 0.5
    assert ctrl.unit_supports_rgb(unit_id=1, network_id="net1") is True
    assert ctrl.unit_supports_rgbw(unit_id=1, network_id="net1") is True
    assert ctrl.unit_supports_color_temperature(unit_id=1, network_id="net1") is True
    assert ctrl.unit_supports_brightness(unit_id=1, network_id="net1") is True
    assert ctrl.unit_supports_distribution(unit_id=1, network_id="net1") is True
    assert ctrl.get_supported_color_temperature(unit_id=1, network_id="net1") == (2200, 6000, 4000)

    # Websockets start, ping, send_message, session_handler, message_handler, stop
    with patch.object(WSClient, "start"):
        await ctrl.start_websockets()

    assert len(ctrl.get_websockets()) == 1
    wire_id = list(ctrl._wire_id_to_network_id.keys())[0]
    ws_obj = ctrl.websocket["net1"]
    ws_obj._state = STATE_RUNNING
    ws_obj.send_message = AsyncMock(return_value=True)

    # Force ping by setting _last_websocket_ping in the past
    ctrl._last_websocket_ping = time.time() - 1000
    await ctrl.ws_ping()
    assert ws_obj.send_message.called

    await ctrl.turn_unit_on(unit_id=1, network_id="net1")
    await ctrl.turn_unit_off(unit_id=1, network_id="net1")
    await ctrl.set_unit_rgbw(unit_id=1, network_id="net1", color_value=(1, 2, 3, 4))
    await ctrl.set_unit_rgb(unit_id=1, network_id="net1", color_value=(1, 2, 3))
    await ctrl.set_unit_color_temperature(unit_id=1, network_id="net1", value=3500)

    # session_handler & message_handler
    ws_obj._data = {
        "method": "unitChanged",
        "id": 1,
        "controls": [{"type": "Dimmer", "value": 0.9}],
    }
    ctrl.session_handler(SIGNAL_DATA, wire_id)
    ws_obj._data = {"method": "peerChanged", "online": True}
    ctrl.session_handler(SIGNAL_DATA, wire_id)
    ctrl.session_handler(SIGNAL_CONNECTION_STATE, wire_id)
    ctrl.session_handler("unknown_signal", wire_id)

    # check_connection and reconnect
    await ctrl.check_connection()  # all running
    ws_obj._state = STATE_DISCONNECTED
    with patch.object(ctrl, "create_session", new=AsyncMock()):
        await ctrl.check_connection()

    await ctrl.stop_websockets()
    assert ctrl.get_websocket_state(network_id="net1") == STATE_STOPPED

    # Additional controller error/retry paths
    assert await ctrl.get_fixture_information(network_id="net1", fixture_id=0) == {}
    with patch.object(ctrl, "request", new=AsyncMock(return_value={"id": 999})):
        assert await ctrl.get_fixture_information(network_id="net1", fixture_id=999) == {"id": 999}
    with patch.object(ctrl, "request", side_effect=RequestedDataNotFound()):
        assert await ctrl.get_fixture_information(network_id="net1", fixture_id=999) == {}
    with patch.object(ctrl, "request", side_effect=Unauthorized()):
        assert await ctrl.get_fixture_information(network_id="net1", fixture_id=999) == {}

    # reconnect retry branches (QuotaLimitsExceeded, ClientConnectorError, TimeoutError)
    conn_err = aiohttp.client_exceptions.ClientConnectorError(MagicMock(), OSError("fail"))
    with patch.object(
        ctrl,
        "create_session",
        side_effect=[QoutaLimitsExceeded(), conn_err, asyncio.TimeoutError(), None],
    ):
        await ctrl.reconnect()

