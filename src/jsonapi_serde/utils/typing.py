import typing

T = typing.TypeVar("T")


def assert_not_none(value: typing.Optional[T]) -> T:
    assert value is not None
    return value
