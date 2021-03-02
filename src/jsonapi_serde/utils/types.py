import typing


class UnspecifiedType:
    _singleton: typing.ClassVar[typing.Optional["UnspecifiedType"]] = None

    def __bool__(self):
        return False

    def __new__(cls) -> "UnspecifiedType":
        if cls._singleton is None:
            cls._singleton = object.__new__(cls)
        return cls._singleton


UNSPECIFIED = UnspecifiedType()
