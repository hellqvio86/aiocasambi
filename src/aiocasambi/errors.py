"""aiocasambi errors."""


class AiocasambiException(Exception):
    """Base error for aiocasambi."""


class RequestError(AiocasambiException):
    """Unable to fulfill request.
    Raised when host or API cannot be reached.
    """


class ResponseError(AiocasambiException):
    """Invalid response."""


class Unauthorized(AiocasambiException):
    """Username is not authorized."""


class LoginRequired(AiocasambiException):
    """User is logged out."""


class NoPermission(AiocasambiException):
    """Users permissions are read only."""


class RateLimit(AiocasambiException):
    """Exceeded server rate limit"""


class CasambiAPIServerError(AiocasambiException):
    """500 errors"""


ERRORS = {
    'api.err.LoginRequired': LoginRequired,
    'api.err.Invalid': Unauthorized,
    'api.err.NoPermission': NoPermission
}


def raise_error(error):
    type = error
    cls = ERRORS.get(type, AiocasambiException)
    raise cls("{}".format(type))
