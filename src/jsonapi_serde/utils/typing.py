import typing

T = typing.TypeVar("T")


def assert_not_none(value: typing.Optional[T]) -> T:
    assert value is not None
    return value


def assert_type(class_: typing.Type[T], value: typing.Any) -> T:
    assert isinstance(value, class_)
    return value
