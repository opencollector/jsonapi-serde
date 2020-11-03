import typing

from .types import JSONValue
from .utils import JSONPointer


class JSONAPISerdeError(Exception):
    pass


class DeserializationErrorItem(typing.Protocol):
    pointer: JSONPointer
    message: str


class DeserializationError(JSONAPISerdeError):
    payload: JSONValue
    errors: typing.Sequence[DeserializationErrorItem]

    def __init__(self, payload: JSONValue, errors: typing.Sequence[DeserializationErrorItem]):
        self.payload = payload
        self.errors = errors
