__all__: tuple[str, ...] = (
    "HTTPError",
    "WebsocketError",
    "BaseClientError",
)


class ParentException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class HTTPError(ParentException):
    pass


class WebsocketError(ParentException):
    pass


class BaseClientError(ParentException):
    pass
