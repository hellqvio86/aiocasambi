"""aiocasambi errors."""


class AiocasambiException(Exception):
    """Base error for aiocasambi."""


class RateLimit(AiocasambiException):
    """Rate limiting exception (deprecated)"""


class ResponseError(AiocasambiException):
    """Error to raise on invalid response (deprecated)"""


class BadRequest(AiocasambiException):
    """400 Bad request, given parameters invalid."""


class Unauthorized(AiocasambiException):
    """401 Unauthorized. Invalid API key or credentials given."""


class ApiNotEnabled(AiocasambiException):
    """
    403 Api not enabled by Casambi administrator or
    trying to create session after failed attempt too soon.
    """


class RequestedDataNotFound(AiocasambiException):
    """404 Requested data not found"""


class MethodNotAllowed(AiocasambiException):
    """405 Method not allowed"""


class InvalidSession(AiocasambiException):
    """410 Invalid Session"""


class RetrievalIntervalIsTooLong(AiocasambiException):
    """416 Retrieval interval is too long"""


class QoutaLimitsExceeded(AiocasambiException):
    """429 Quota limits exceeded"""


class CasambiAPIServerError(AiocasambiException):
    """500 Server error"""


ERRORS = {
    400: BadRequest,
    401: Unauthorized,
    403: ApiNotEnabled,
    404: RequestedDataNotFound,
    405: MethodNotAllowed,
    410: InvalidSession,
    416: RetrievalIntervalIsTooLong,
    429: QoutaLimitsExceeded,
    500: CasambiAPIServerError,
}

ERROR_CODES = ERRORS.keys()


def get_error(status_code: int):
    """Function for raise error"""
    error = ERRORS.get(status_code, AiocasambiException)

    return error
