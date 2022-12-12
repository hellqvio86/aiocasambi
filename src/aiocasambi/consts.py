"""
Constants to aiocasambi
"""
SIGNAL_DATA = "data"
SIGNAL_CONNECTION_STATE = "state"
SIGNAL_UNIT_PULL_UPDATE = "unit pull update"

STATE_DISCONNECTED = "disconnected"
STATE_RUNNING = "running"
STATE_STARTING = "starting"
STATE_STOPPED = "stopped"

MAX_NETWORK_IDS = 100
MAX_RETRIES = 10

CASAMBI_REASONS_BY_STATUS_CODE = {
    200: "request OK",
    400: "Bad request, given parameters invalid",
    401: "Unauthorized. Invalid API key or credentials given",
    403: "Api not enabled by Casambi administrator or trying to create session after failed attempt too soon",
    404: "Requested data not found",
    405: "Method not allowed",
    410: "Invalid session",
    416: "Retrieval interval is too long",
    429: "Quota limits exceeded",
    500: "Server error",
}

CASAMBI_FIXTURE_IDS = {
    2516: {"oem": "Vadsbo", "fixture_model": "LD220WCM_onoff", "type": "Luminaire"},
    4027: {"oem": "Casambi", "fixture_model": "CBU-PWM4 RGBW", "type": "Luminaire"},
    14235: {"oem": "AIMOTION", "fixture_model": "GLOW", "type": "Luminaire"},
}
