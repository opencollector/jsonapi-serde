import typing

T = typing.TypeVar("T")


class Deferred(typing.Generic[T]):
    _yielder: typing.Optional[typing.Callable[[], T]] = None
    _value_yielded: bool = False
    _value: typing.Optional[T] = None

    def __getattr__(self, k) -> "Deferred":
        return Deferred(lambda: getattr(self(), k))

    def __init__(self, yielder: typing.Callable[[], T]):
        self._yielder = yielder

    def __call__(self) -> T:
        if not self._value_yielded:
            assert self._yielder is not None
            self._value = self._yielder()
            self._value_yielded = True
        return typing.cast(T, self._value)
