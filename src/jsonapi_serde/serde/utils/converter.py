import abc
import base64
import collections.abc
import dataclasses
import datetime
import decimal
import json
import math
import typing

import iso8601  # type: ignore

from ..types import JSONArray, JSONObject, JSONValue
from .jsonpointer import JSONPointer

JsonicScalar = typing.Union[
    bool, int, float, str, bytes, datetime.datetime, datetime.date, decimal.Decimal, None
]
JsonicArray = typing.Sequence[typing.Any]  # FIXME: typing.Any is actually JsonicValue
JsonicSet = typing.Set[typing.Any]  # FIXME: typing.Any is actually JsonicValue
JsonicObject = typing.Mapping[str, typing.Any]  # FIXME: typing.Any is actually JsonicValue
TypedClass = object
JsonicValue = typing.Union[JsonicScalar, JsonicArray, JsonicSet, JsonicObject, TypedClass]
JsonicType = typing.Union[typing.Type[JsonicValue], typing._GenericAlias, typing._SpecialForm]  # type: ignore


class JsonicDataValidationError(Exception):
    _pointer: JSONPointer
    _message: str

    def __init__(self, pointer: JSONPointer, message: str):
        self._pointer = pointer
        self._message = message

    @property
    def pointer(self) -> JSONPointer:
        return self._pointer

    @property
    def message(self) -> str:
        return self._message

    def __str__(self):
        return f"{self._message} at {self._pointer}"


Tex = typing.TypeVar("Tex", bound=Exception)


def cause(ex: Tex, cause: Exception) -> Tex:
    ex.__cause__ = cause
    return ex


def english_enumerate(items: typing.Iterable[str], conj: str = ", and ") -> str:
    buf = []

    i = iter(items)
    try:
        x = next(i)
    except StopIteration:
        return ""
    buf.append(x)

    lx: typing.Optional[str] = None

    for x in i:
        if lx is not None:
            buf.append(", ")
            buf.append(lx)
        lx = x
    if lx is not None:
        buf.append(conj)
        buf.append(lx)
    return "".join(buf)


class DateTimeConstructorProtocol(typing.Protocol):
    def __call__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        second: int,
        microsecond: int,
        tzinfo: typing.Optional[datetime.tzinfo],
    ):
        ...


Tdt = typing.TypeVar("Tdt")  # Tdt implements DateTimeConstructorProtocol


def datetime_clone(typ: typing.Type[Tdt], orig: datetime.datetime) -> Tdt:
    return typing.cast(DateTimeConstructorProtocol, typ)(
        year=orig.year,
        month=orig.month,
        day=orig.day,
        hour=orig.hour,
        minute=orig.minute,
        second=orig.second,
        microsecond=orig.microsecond,
        tzinfo=orig.tzinfo,
    )


class DateConstructorProtocol(typing.Protocol):
    def __call__(self, year: int, month: int, day: int):
        ...  # pragma: nocover


Td = typing.TypeVar("Td")  # Td implements DateConstructorProtocol


def date_clone(typ: typing.Type[Td], orig: datetime.datetime) -> Td:
    return typing.cast(DateConstructorProtocol, typ)(
        year=orig.year,
        month=orig.month,
        day=orig.day,
    )


def is_optional(typ: JsonicType) -> bool:
    return isinstance(typ, typing._GenericAlias) and isinstance(typing.get_origin(typ), typing._SpecialForm) and typing.get_origin(typ)._name == "Union" and type(None) in typ.__args__  # type: ignore


CustomConverterNameResolverFunc = typing.Callable[[JsonicType], str]
CustomConverterConvertFunc = typing.Callable[
    ["PyTypedJsonicDataConverter", "ConverterContext", JSONPointer, JsonicType, JSONValue],
    typing.Tuple[JsonicValue, float],
]


class CustomConverter(typing.Protocol):
    def resolve_name(self, typ: JsonicType) -> str:
        ...  # pragma: nocover

    def __call__(
        self,
        converter: "PyTypedJsonicDataConverter",
        ctx: "ConverterContext",
        pointer: JSONPointer,
        typ: JsonicType,
        value: JSONValue,
    ) -> typing.Tuple[JsonicValue, float]:
        ...  # pragma: nocover


class CustomConverterFuncAdapter:
    convert: CustomConverterConvertFunc  # type: ignore

    def resolve_name(self, typ: JsonicType) -> str:
        ...  # pragma: nocover

    def __call__(
        self,
        converter: "PyTypedJsonicDataConverter",
        ctx: "ConverterContext",
        pointer: JSONPointer,
        typ: JsonicType,
        value: JSONValue,
    ) -> typing.Tuple[JsonicValue, float]:
        return self.convert(converter, ctx, pointer, typ, value)  # type: ignore

    def __init__(
        self, resolve_name: CustomConverterNameResolverFunc, convert: CustomConverterConvertFunc
    ):
        self.resolve_name = resolve_name  # type: ignore
        self.convert = convert  # type: ignore


class NameMapper(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def resolve(
        self,
        converter: "PyTypedJsonicDataConverter",
        pointer: JSONPointer,
        typ: JsonicType,
        name: str,
    ) -> typing.Optional[str]:
        ...

    @abc.abstractmethod
    def reverse_resolve(
        self,
        converter: "PyTypedJsonicDataConverter",
        pointer: JSONPointer,
        typ: JsonicType,
        name: str,
    ) -> typing.Optional[str]:
        ...


NameMapperResolveFunc = typing.Callable[
    ["PyTypedJsonicDataConverter", JSONPointer, JsonicType, str], typing.Optional[str]
]


class NameMapperFuncAdapter(NameMapper):
    def resolve(
        self,
        converter: "PyTypedJsonicDataConverter",
        pointer: JSONPointer,
        typ: JsonicType,
        name: str,
    ) -> typing.Optional[str]:
        ...

    def reverse_resolve(
        self,
        converter: "PyTypedJsonicDataConverter",
        pointer: JSONPointer,
        typ: JsonicType,
        name: str,
    ) -> typing.Optional[str]:
        ...

    def __init__(self, resolve: NameMapperResolveFunc, reverse_resolve: NameMapperResolveFunc):
        self.resolve = resolve  # type: ignore
        self.reverse_resolve = reverse_resolve  # type: ignore


class IdentityNameMapper(tuple, NameMapper):
    def resolve(
        self,
        converter: "PyTypedJsonicDataConverter",
        pointer: JSONPointer,
        typ: JsonicType,
        name: str,
    ) -> str:
        return name

    def reverse_resolve(
        self,
        converter: "PyTypedJsonicDataConverter",
        pointer: JSONPointer,
        typ: JsonicType,
        name: str,
    ) -> str:
        return name


identity_mapper = IdentityNameMapper()


T = typing.TypeVar("T", bound=JsonicValue)


class ConverterContext(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def stopped(self) -> bool:
        ...

    @abc.abstractmethod
    def validation_error_occurred(self, error: JsonicDataValidationError) -> None:
        ...


class DefaultConverterContext(ConverterContext):
    @property
    def stopped(self):
        return False

    def validation_error_occurred(self, error: JsonicDataValidationError) -> None:
        raise error


class ErrorCollectingConverterContext(ConverterContext):
    @property
    def stopped(self):
        return False

    def validation_error_occurred(self, error: JsonicDataValidationError) -> None:
        self.errors.append(error)

    def __init__(self):
        self.errors = []


Visitor = typing.Callable[
    ["PyTypedJsonicDataConverter", "ConverterContext", JSONPointer, JsonicType, JsonicValue],
    JsonicValue,
]


class PyTypedJsonicDataConverter:
    custom_types: typing.Mapping[JsonicType, CustomConverter] = {}
    name_mappers: typing.Mapping[JsonicType, NameMapper] = {}
    visitor: typing.Optional[Visitor] = None

    pytype_to_json_type_mappings: typing.Dict[typing.Type, str] = {
        int: "number",
        float: "number",
        str: "string",
        bytes: "string",
        decimal.Decimal: "number or string",
        datetime.datetime: "number or string",
        datetime.date: "string",
        type(None): "null",
    }
    abctype_to_json_type_mappings: typing.Sequence[typing.Tuple[abc.ABCMeta, str]] = (
        (collections.abc.Sequence, "array"),
        (collections.abc.Mapping, "object"),
        (collections.abc.Set, "array"),
    )

    def py_type_repr(self, typ: typing.Type) -> str:
        typename = self.pytype_to_json_type_mappings.get(typ)
        if typename is not None:
            return typename
        for t, typename in self.abctype_to_json_type_mappings:
            if issubclass(typ, t):
                return typename
        return f"unknown type: {typ}"

    def type_repr(self, typ: typing._GenericAlias) -> str:  # type: ignore
        custom_converter = self.custom_types.get(typ)
        if custom_converter is not None:
            return custom_converter.resolve_name(typ)
        for typ_, custom_converter in self.custom_types.items():
            if not isinstance(typ_, (typing._GenericAlias, typing._SpecialForm)) and isinstance(typ, type) and issubclass(typ, typ_):  # type: ignore
                return custom_converter.resolve_name(typ)
        if isinstance(typ, typing._GenericAlias):  # type: ignore
            origin = typing.get_origin(typ)
            if isinstance(origin, typing._SpecialForm) and str(origin) == "typing.Union":
                return f"any of {english_enumerate((self.type_repr(t) for t in typing.get_args(typ)), conj=', or ')}"
            elif issubclass(
                typing.cast(abc.ABCMeta, origin), (collections.abc.Sequence, collections.abc.Set)
            ):
                args = typing.get_args(typ)
                if len(args) == 1:
                    return f"array of {self.type_repr(args[0])}"
            elif issubclass(typing.cast(abc.ABCMeta, origin), collections.abc.Mapping):
                args = typing.get_args(typ)
                if len(args) == 2:
                    return f"object of {{{self.type_repr(args[0])}: {self.type_repr(args[1])}}}"
            return f"unknown type: {typ.__origin__}"
        elif isinstance(typ, typing._SpecialForm):
            if str(typ) == "typing.Any":
                return "any value"
            return f"unknown type: {typ}"
        else:
            return self.py_type_repr(typ)

    def _lookup_name_mapper(self, typ: typing.Union[JsonicType, typing._TypedDictMeta, typing._SpecialForm, typing._GenericAlias]) -> typing.Optional[NameMapper]:  # type: ignore
        name_mapper = self.name_mappers.get(typ)
        if name_mapper is not None:
            return name_mapper
        name_mapper = self.name_mappers.get(typing.Any)
        if name_mapper is not None:
            return name_mapper
        name_mapper = self.name_mappers.get(object)
        if name_mapper is not None:
            return name_mapper
        return None

    def _convert_with_pytype(
        self, ctx: ConverterContext, pointer: JSONPointer, typ: typing.Type, value: JsonicValue
    ) -> typing.Tuple[JsonicValue, float]:
        if isinstance(value, typ):
            return value, 0.5
        if isinstance(value, str):
            if issubclass(typ, datetime.datetime):
                try:
                    return datetime_clone(typ, iso8601.parse_date(value)), 3.0
                except iso8601.ParseError as e:
                    ctx.validation_error_occurred(
                        cause(
                            JsonicDataValidationError(
                                pointer, f"bad date time string ({json.dumps(value)})"
                            ),
                            e,
                        )
                    )
                    return (None, math.inf)

            elif issubclass(typ, datetime.date):
                try:
                    return date_clone(typ, iso8601.parse_date(value)), 3.0
                except iso8601.ParseError as e:
                    ctx.validation_error_occurred(
                        cause(
                            JsonicDataValidationError(
                                pointer, f"bad date time string ({json.dumps(value)})"
                            ),
                            e,
                        )
                    )
                    return (None, math.inf)
            elif issubclass(typ, decimal.Decimal):
                try:
                    return typ(value), 2.0
                except (ValueError, decimal.InvalidOperation) as e:
                    ctx.validation_error_occurred(
                        cause(
                            JsonicDataValidationError(
                                pointer, f"bad decimal string ({json.dumps(value)})"
                            ),
                            e,
                        )
                    )
                    return (None, math.inf)
            elif issubclass(typ, bytes):
                try:
                    return base64.b64decode(value.encode("ascii")), 2.0
                except ValueError as e:
                    ctx.validation_error_occurred(
                        cause(
                            JsonicDataValidationError(
                                pointer, f"bad base64 string ({json.dumps(value)})"
                            ),
                            e,
                        )
                    )
                    return (None, math.inf)
        elif isinstance(value, (int, float)):
            if issubclass(typ, (int, float)):
                return typ(value), 2.0
            elif issubclass(typ, datetime.datetime):
                return typ.utcfromtimestamp(value).replace(tzinfo=datetime.timezone.utc), 3.0
            elif issubclass(typ, decimal.Decimal):
                try:
                    return typ(value), 2.0
                except (ValueError, decimal.InvalidOperation) as e:
                    ctx.validation_error_occurred(
                        cause(
                            JsonicDataValidationError(
                                pointer, f"bad decimal string ({json.dumps(value)})"
                            ),
                            e,
                        )
                    )
                    return (None, math.inf)
        ctx.validation_error_occurred(
            JsonicDataValidationError(
                pointer,
                f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where {self.py_type_repr(typ)} expected",
            )
        )
        return (None, math.inf)

    def _convert_with_array(
        self, ctx: ConverterContext, pointer: JSONPointer, typ: JsonicType, value: JSONArray
    ) -> typing.Tuple[JsonicArray, float]:
        retval: typing.MutableSequence[JsonicValue] = []
        confidence = 1.0
        for i, item in enumerate(value):
            pair = self._convert(ctx, pointer[i], typ, item)
            retval.append(pair[0])
            confidence *= pair[1]
        return (retval, confidence ** (1 / float(len(value))) if value else 2.0)

    def _convert_with_set(
        self, ctx: ConverterContext, pointer: JSONPointer, typ: JsonicType, value: JSONArray
    ) -> typing.Tuple[JsonicSet, float]:
        occurred_item: typing.MutableMapping[JsonicValue, int] = {}
        retval: typing.MutableSet[JsonicValue] = set()
        confidence = 1.0
        for i, item in enumerate(value):
            p = pointer[i]
            pair = self._convert(ctx, p, typ, item)
            if pair[0] in occurred_item:
                ctx.validation_error_occurred(
                    JsonicDataValidationError(
                        p,
                        f"identical item {item} already occurred at index {occurred_item[pair[0]]}",
                    )
                )
                if ctx.stopped:
                    break
                else:
                    continue
            occurred_item[pair[0]] = i
            retval.add(pair[0])
            confidence *= pair[1]
        return (
            typing.cast(JsonicSet, retval),
            confidence ** (1 / float(len(value))) if value else 2.0,
        )  # this cast should've been unnecessary, because Sequences are casted implicitly in a covariant context.

    def _convert_with_homogenious_object(
        self,
        ctx: ConverterContext,
        pointer: JSONPointer,
        key_type: JsonicType,
        value_type: JsonicType,
        value: JSONObject,
    ) -> typing.Tuple[JsonicObject, float]:
        retval: typing.MutableMapping[str, JsonicValue] = {}
        confidence = 1.0
        for k, v in value.items():
            jk_pair = self._convert(ctx, pointer, key_type, k)
            if not isinstance(jk_pair[0], str):
                ctx.validation_error_occurred(
                    JsonicDataValidationError(
                        pointer,
                        f"key has type {self.type_repr(key_type)}, which deduces {k} into {self.type_repr(type(jk_pair[0]))}",
                    )
                )
                if ctx.stopped:
                    break
                else:
                    continue
            jv_pair = self._convert(ctx, pointer / jk_pair[0], value_type, v)
            typ = typing.Mapping[key_type, value_type]  # type: ignore
            name_mapper = self._lookup_name_mapper(typ)
            n: str
            if name_mapper is None:
                n = jk_pair[0]
            else:
                _n = name_mapper.resolve(self, pointer, typ, jk_pair[0])
                if _n is None:
                    continue
                n = _n
            retval[n] = jv_pair[0]
            confidence *= math.sqrt(jk_pair[1] * jv_pair[1])
        return (retval, confidence ** (1 / float(len(value))) if value else 2.0)

    def _convert_with_generic_type(self, ctx: ConverterContext, pointer: JSONPointer, typ: typing._GenericAlias, value: JSONValue) -> typing.Tuple[JsonicValue, float]:  # type: ignore
        origin = typing.cast(abc.ABCMeta, typing.get_origin(typ))
        args = typing.get_args(typ)
        if issubclass(origin, tuple):
            if len(args) == 2 and args[1] is ...:
                elem_type = args[0]
                if not isinstance(value, collections.abc.Sequence):
                    ctx.validation_error_occurred(
                        JsonicDataValidationError(
                            pointer,
                            f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where an array of {self.type_repr(elem_type)} expected",
                        )
                    )
                    return (None, math.inf)
                pair = self._convert_with_array(ctx, pointer, elem_type, value)
                confidence = pair[1]
                if isinstance(value, tuple):
                    confidence *= 0.5
                return (tuple(pair[0]), confidence)
            else:
                if not isinstance(value, collections.abc.Sequence) or len(args) != len(value):
                    ctx.validation_error_occurred(
                        JsonicDataValidationError(
                            pointer,
                            f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where an array [{', '.join(self.type_repr(elem_type) for elem_type in args)}] expected",
                        )
                    )
                    return (None, math.inf)
                confidence = 1.0
                retval: typing.MutableSequence[JsonicValue] = []
                for i, (elem_type, v) in enumerate(zip(args, value)):
                    _pair = self._convert_inner(ctx, pointer[i], elem_type, v)
                    retval.append(_pair[0])
                    confidence *= _pair[1]
                return (tuple(retval), confidence ** (1 / float(len(value))) if value else 2.0)
        elif issubclass(origin, collections.abc.Sequence):
            assert len(args) == 1
            elem_type = args[0]
            if not isinstance(value, collections.abc.Sequence):
                ctx.validation_error_occurred(
                    JsonicDataValidationError(
                        pointer,
                        f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where an array of {self.type_repr(elem_type)} expected",
                    )
                )
                return (None, math.inf)
            return self._convert_with_array(ctx, pointer, elem_type, value)
        elif issubclass(origin, collections.abc.Set):
            assert len(args) == 1
            elem_type = args[0]
            if not isinstance(value, collections.abc.Sequence):
                ctx.validation_error_occurred(
                    JsonicDataValidationError(
                        pointer,
                        f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where an array of {self.type_repr(elem_type)} expected",
                    )
                )
                return (None, math.inf)
            return self._convert_with_set(ctx, pointer, elem_type, value)
        elif issubclass(origin, collections.abc.Mapping):
            assert len(args) == 2
            key_type, elem_type = args
            if not isinstance(value, collections.abc.Mapping):
                ctx.validation_error_occurred(
                    JsonicDataValidationError(
                        pointer,
                        f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where an mapping of {{{self.type_repr(key_type)}: {self.type_repr(elem_type)}}} expected",
                    )
                )
                return (None, math.inf)
            return self._convert_with_homogenious_object(ctx, pointer, key_type, elem_type, value)

        ctx.validation_error_occurred(
            JsonicDataValidationError(
                pointer,
                f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where {self.type_repr(typ)} expected",
            )
        )
        return (None, math.inf)

    def _convert_with_union(self, ctx: ConverterContext, pointer: JSONPointer, typ: typing._GenericAlias, value: JSONValue) -> typing.Iterable[typing.Tuple[JsonicValue, float]]:  # type: ignore
        args = typing.get_args(typ)
        if len(args) == 2 and None.__class__ in args:
            # special case: typing.Optional
            if value is None:
                yield None, 1.0
                return
            t = args[1] if args[0] is None.__class__ else args[0]
            yield self._convert(ctx, pointer, t, value)
        else:
            for i, t in enumerate(args):
                try:
                    pair = self._convert(DefaultConverterContext(), pointer, t, value)
                    yield pair[0], (pair[1] * len(args) + i)
                except JsonicDataValidationError:
                    continue

    def _convert_with_typeddict(self, ctx: ConverterContext, pointer: JSONPointer, typ: typing._TypedDictMeta, value: JSONValue) -> typing.Tuple[typing.Optional[JsonicObject], float]:  # type: ignore
        if not isinstance(value, collections.abc.Mapping):
            ctx.validation_error_occurred(
                JsonicDataValidationError(
                    pointer,
                    f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where {self.type_repr(typ)} expected",
                )
            )
            return (None, math.inf)
        entries: typing.List[typing.Tuple[str, JsonicValue]] = []
        confidence = 1.0
        for n, vtyp in typing.get_type_hints(typ).items():
            v: JsonicValue
            name_mapper = self._lookup_name_mapper(typ)
            k: str
            if name_mapper is None:
                k = n
            else:
                _k = name_mapper.reverse_resolve(self, pointer, typ, n)
                if _k is None:
                    continue
                k = _k
            if k not in value:
                if is_optional(vtyp):
                    continue
                ctx.validation_error_occurred(
                    JsonicDataValidationError(pointer, f"property {k} does not exist in {value}")
                )
                if ctx.stopped:
                    break
                else:
                    continue
            else:
                jv_pair = self._convert(ctx, pointer / k, vtyp, value[k])
                entries.append((n, jv_pair[0]))
                confidence *= jv_pair[1]
        return typ(entries), confidence ** (1 / float(len(entries))) if entries else 1.0

    def _convert_with_dataclass(
        self,
        ctx: ConverterContext,
        pointer: JSONPointer,
        typ: typing.Type[TypedClass],
        value: JSONValue,
    ) -> typing.Tuple[typing.Optional[JsonicObject], float]:
        if not isinstance(value, collections.abc.Mapping):
            ctx.validation_error_occurred(
                JsonicDataValidationError(
                    pointer,
                    f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where {self.type_repr(typ)} expected",
                )
            )
            return (None, math.inf)
        attrs: typing.MutableMapping[str, JsonicValue] = {}
        confidence = 1.0
        for field in dataclasses.fields(typ):
            if not field.init:
                continue
            n = field.name
            jv_pair: typing.Tuple[JsonicValue, float]
            k: str
            name_mapper = self._lookup_name_mapper(typ)
            if name_mapper is None:
                k = n
            else:
                _k = name_mapper.reverse_resolve(self, pointer, typ, n)
                if _k is None:
                    continue
                k = _k
            if k not in value:
                if (
                    field.default is not dataclasses.MISSING
                    or field.default_factory is not dataclasses.MISSING  # type: ignore
                ):
                    continue
                if field.default is not dataclasses.MISSING:
                    jv_pair = (field.default, 1.0)
                elif field.default_factory is not dataclasses.MISSING:  # type: ignore
                    jv_pair = (field.default_factory(), 1.0)  # type: ignore
                else:
                    ctx.validation_error_occurred(
                        JsonicDataValidationError(
                            pointer, f"property {k} does not exist in {value}"
                        )
                    )
                    if ctx.stopped:
                        break
                    else:
                        continue
            else:
                jv_pair = self._convert(ctx, pointer / k, field.type, value[k])
            attrs[n] = jv_pair[0]
            confidence *= jv_pair[1]
        try:
            return (
                typing.cast(typing.Callable, typ)(**attrs),
                confidence ** (1 / float(len(attrs))) if attrs else 1.0,
            )
        except ValueError as e:
            ctx.validation_error_occurred(JsonicDataValidationError(pointer, str(e)))
            return (None, math.inf)

    def _convert_inner(
        self, ctx: ConverterContext, pointer: JSONPointer, typ: JsonicType, value: JSONValue
    ) -> typing.Tuple[JsonicValue, float]:
        custom_converter = self.custom_types.get(typ)
        if custom_converter is not None:
            return custom_converter(self, ctx, pointer, typ, value)
        for typ_, custom_converter in self.custom_types.items():
            if not isinstance(typ_, (typing._GenericAlias, typing._SpecialForm)) and isinstance(typ, type) and issubclass(typ, typ_):  # type: ignore
                return custom_converter(self, ctx, pointer, typ, value)
        if isinstance(typ, typing._GenericAlias):  # type: ignore
            origin = typing.get_origin(typ)
            if isinstance(origin, typing._SpecialForm) and str(origin) == "typing.Union":
                candidates = sorted(
                    self._convert_with_union(ctx, pointer, typ, value), key=lambda pair: pair[1]
                )
                if len(candidates) == 0:
                    ctx.validation_error_occurred(
                        JsonicDataValidationError(
                            pointer,
                            f"value has type {self.py_type_repr(type(value))} ({json.dumps(value)}) where {self.type_repr(typ)} expected",
                        )
                    )
                    return (None, math.inf)
                return candidates[0]
            else:
                return self._convert_with_generic_type(ctx, pointer, typ, value)
        elif isinstance(typ, typing._SpecialForm):
            assert str(typ) == "typing.Any"
            return value, 1.0
        elif isinstance(typ, typing._TypedDictMeta):  # type: ignore
            return self._convert_with_typeddict(ctx, pointer, typ, value)
        elif dataclasses.is_dataclass(typ):
            return self._convert_with_dataclass(ctx, pointer, typ, value)
        else:
            return self._convert_with_pytype(ctx, pointer, typ, value)

    def _convert(
        self, ctx: ConverterContext, pointer: JSONPointer, typ: JsonicType, value: JSONValue
    ) -> typing.Tuple[JsonicValue, float]:
        pair = self._convert_inner(ctx, pointer, typ, value)
        if self.visitor is not None:
            return self.visitor(self, ctx, pointer, typ, pair[0]), pair[1]
        else:
            return pair

    @typing.overload
    def convert(self, ctx: ConverterContext, typ: typing.Union[typing._GenericAlias, typing._SpecialForm], value: JSONValue) -> typing.Any:  # type: ignore
        ...  # pragma: nocover

    @typing.overload
    def convert(self, ctx: ConverterContext, typ: typing.Type[T], value: JSONValue) -> T:
        ...  # pragma: nocover

    def convert(self, ctx: ConverterContext, typ: JsonicType, value: JSONValue) -> typing.Any:
        pair = self._convert(ctx, JSONPointer(), typ, value)
        return pair[0]

    @typing.overload
    def __call__(self, typ: typing.Union[typing._GenericAlias, typing._SpecialForm], value: JSONValue) -> typing.Any:  # type: ignore
        ...  # pragma: nocover

    @typing.overload
    def __call__(self, typ: typing.Type[T], value: JSONValue) -> T:
        ...  # pragma: nocover

    def __call__(self, typ: JsonicType, value: JSONValue) -> typing.Any:
        return self.convert(DefaultConverterContext(), typ, value)

    def __init__(
        self,
        custom_types: typing.Mapping[JsonicType, CustomConverter] = {},
        name_mappers: typing.Mapping[JsonicType, NameMapper] = {},
        visitor: typing.Optional[Visitor] = None,
    ):
        self.custom_types = custom_types
        self.name_mappers = name_mappers
        self.visitor = visitor
