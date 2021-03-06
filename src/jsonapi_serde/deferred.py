import typing

T = typing.TypeVar("T")


class Deferred(typing.Generic[T]):
    _yielder: typing.Optional[typing.Callable[..., T]] = None
    _value_yielded: bool = False
    _value: typing.Optional[T] = None
    _args: typing.Sequence[typing.Any]
    _kwargs: typing.Mapping[str, typing.Any]

    def __getattr__(self, k) -> "Deferred":
        return Deferred(lambda: getattr(self(), k))

    def __init__(self, yielder: typing.Callable[..., T], *args, **kwargs):
        self._yielder = yielder
        self._args = args
        self._kwargs = kwargs

    def __call__(self) -> T:
        if not self._value_yielded:
            assert self._yielder is not None
            self._value = self._yielder(*self._args, **self._kwargs)
            self._value_yielded = True
        return typing.cast(T, self._value)


class NeverType:
    pass


Never = NeverType()


class Promise(Deferred[T]):
    _set_value: typing.Union[T, NeverType] = Never

    def _yield_value(self) -> T:
        raise RuntimeError("value is not set")

    def set(self, value: T) -> None:
        self._value = value
        self._value_yielded = True

    def __init__(self):
        super().__init__(self._yield_value)
