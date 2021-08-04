import typing

T = typing.TypeVar("T")


class Deferred(typing.Generic[T]):
    """
    A deferred object encapsulates a lazy evaluated value.
    It takes a function that yields the value for its constructor argument, and
    it behaves as a callable by which it resolves to the yielded value.

    An attribute access to a :py:class:`Deferred` recursively results in another
    :py:class:`Deferred` that encapsulates the access to the attribute.

    :param Callable[..., T] yielder: a callable that resolves the value.
    :param args: positional arguments for the yielder.
    :param kwargs: keyword arguments for the yielder.
    """

    _yielder: typing.Optional[typing.Callable[..., T]] = None
    _value_yielded: bool = False
    _value: typing.Optional[T] = None
    _args: typing.Sequence[typing.Any]
    _kwargs: typing.Mapping[str, typing.Any]

    def __getattr__(self, k) -> "Deferred":
        return Deferred(lambda: getattr(self(), k))

    def __init__(self, yielder: typing.Callable[..., T], *args, **kwargs) -> None:
        """
        Constructor.

        :param Callable[..., T] yielder: a callable that resolves the value.
        :param args: positional arguments for the yielder.
        :param kwargs: keyword arguments for the yielder.
        """
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
    """
    A :py:class:`Promise` is a special case of :py:class:`Deferred`, in that
    you can inject the resolved value directly into the object by calling :py:meth:`set`.
    """

    _set_value: typing.Union[T, NeverType] = Never

    def _yield_value(self) -> T:
        raise RuntimeError("value is not set")

    def set(self, value: T) -> None:
        self._value = value
        self._value_yielded = True

    def __init__(self):
        super().__init__(self._yield_value)
