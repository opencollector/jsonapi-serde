import abc
import collections.abc
import datetime
import enum
import typing

from .declarative import ConverterFactory
from .exceptions import ConversionError, UnknownResourceTypeError
from .interfaces import (
    Endpoint,
    NativeAttributeDescriptor,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipDescriptor,
    PaginatedEndpoint,
)
from .mapper import (
    EndpointResolver,
    Mapper,
    SerdeTypeResolver,
    ToNativeContext,
    ToSerdeContext,
)
from .models import (
    ResourceAttributeDescriptor,
    ResourceDescriptor,
    ResourceToManyRelationshipDescriptor,
    ResourceToOneRelationshipDescriptor,
)
from .serde.models import AttributeValue, Source
from .serde.types import JSONScalar
from .serde.utils import JsonicScalar, PyTypedJsonicDataConverter


class DefaultSerdeTypeResolverImpl(SerdeTypeResolver):
    mappers: typing.Dict[str, Mapper]

    def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
        return descr.name

    def query_descriptor_by_type_name(self, name: str) -> ResourceDescriptor:
        try:
            return self.mappers[name].resource_descr
        except KeyError:
            raise UnknownResourceTypeError(name)

    def mapper_added(self, mapper: Mapper) -> None:
        self.mappers[mapper.resource_descr.name] = mapper

    def __init__(self):
        self.mappers = {}


class DefaultEndpointResolverImpl(EndpointResolver):
    def resolve_singleton_endpoint(self, mapper: Mapper) -> typing.Optional[Endpoint]:
        return None

    def resolve_collection_endpoint(self, mapper: Mapper) -> typing.Optional[PaginatedEndpoint]:
        return None

    def resolve_to_one_relationship_endpoint(
        self,
        mapper: Mapper,
        native_descr: NativeToOneRelationshipDescriptor,
        rel_descr: ResourceToOneRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[Endpoint]:
        return None

    def resolve_to_many_relationship_endpoint(
        self,
        mapper: Mapper,
        native_descr: NativeToManyRelationshipDescriptor,
        rel_descr: ResourceToManyRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[PaginatedEndpoint]:
        return None


Tn = typing.TypeVar("Tn")


class BasicTypeConverter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def convert_to_attribute_value(
        self, typ: typing.Type[AttributeValue], allow_null: bool, value: typing.Any
    ) -> AttributeValue:
        ...

    @abc.abstractmethod
    def convert_from_attribute_value(
        self, typ: typing.Type[Tn], value: AttributeValue
    ) -> typing.Optional[Tn]:
        ...


class DefaultBasicTypeConverterImpl(BasicTypeConverter):
    jsonic_converter: PyTypedJsonicDataConverter

    def convert_to_attribute_value(
        self, typ: typing.Type[AttributeValue], allow_null: bool, value: typing.Any
    ) -> AttributeValue:
        if value is None and allow_null:
            return None
        elif isinstance(value, enum.Enum):
            return value.value
        elif isinstance(value, (datetime.datetime, datetime.date)):
            return value
        elif issubclass(typ, typing.get_args(JsonicScalar)) and isinstance(
            value, typing.get_args(JSONScalar)
        ):
            return self.jsonic_converter(typ, value)
        elif (
            not issubclass(typ, str)
            and issubclass(typ, (collections.abc.Sequence, collections.abc.Mapping))
            and not isinstance(value, str)
            and isinstance(value, (collections.abc.Sequence, collections.abc.Mapping))
        ):
            return typing.cast(AttributeValue, value)  # TODO
        raise TypeError(f"failed to render a native value to an attribute value ({typ})")

    def convert_from_attribute_value(
        self, typ: typing.Type[Tn], value: AttributeValue
    ) -> typing.Optional[Tn]:
        if value is None:
            return None
        elif issubclass(typ, enum.Enum) and isinstance(value, str):
            for e in typ:
                if e.value == value:
                    return typing.cast(Tn, e)
            raise ValueError(f"{value} is not a valid name for the enum {typ}")
        elif issubclass(typ, typing.get_args(JsonicScalar)) and isinstance(
            value, typing.get_args(JSONScalar)
        ):
            return self.jsonic_converter(typ, typing.cast(JSONScalar, value))
        elif isinstance(value, typ) or (
            not issubclass(typ, str)
            and issubclass(typ, (collections.abc.Sequence, collections.abc.Mapping))
            and not isinstance(value, str)
            and isinstance(value, (collections.abc.Sequence, collections.abc.Mapping))
        ):
            return typing.cast(Tn, value)  # TODO
        raise TypeError(f"unsupported conversion from {type(value)} to {typ}")

    def __init__(self):
        self.jsonic_converter = PyTypedJsonicDataConverter()


class DefaultConverterFactoryImpl(ConverterFactory):
    converter: BasicTypeConverter

    def build_one_to_one_serde_converter(
        self,
        resource_attr_descr: ResourceAttributeDescriptor,
        native_attr_descr: NativeAttributeDescriptor,
    ) -> typing.Callable[[ToSerdeContext, typing.Any], AttributeValue]:
        def _(ctx: ToSerdeContext, value: typing.Any) -> AttributeValue:
            try:
                return self.converter.convert_to_attribute_value(
                    resource_attr_descr.type, resource_attr_descr.allow_null, value
                )
            except (ValueError, TypeError) as e:
                raise ConversionError(
                    ctx=ctx,
                    resource_attribute_descrs=[resource_attr_descr],
                    native_attribute_descrs=[native_attr_descr],
                ) from e

        return _

    def build_one_to_many_serde_converter(
        self,
        resource_attr_descrs: typing.Sequence[ResourceAttributeDescriptor],
        native_attr_descr: NativeAttributeDescriptor,
    ) -> typing.Callable[[ToSerdeContext, typing.Any], typing.Sequence[AttributeValue]]:
        def _(ctx: ToSerdeContext, value: typing.Any) -> typing.Sequence[AttributeValue]:
            try:
                if isinstance(native_attr_descr.type, collections.abc.Mapping):
                    if not isinstance(value, collections.abc.Sequence):
                        raise TypeError(f"{value!r} is not a sequence")
                    if len(value) != len(resource_attr_descrs):
                        raise ValueError(
                            f"{value!r} does not contain {len(resource_attr_descrs)} items"
                        )
                    return {
                        resource_attr_descr.name: self.converter.convert_to_attribute_value(
                            resource_attr_descr.type, resource_attr_descr.allow_null, v
                        )
                        for v, resource_attr_descr in zip(value, resource_attr_descrs)
                    }
                elif isinstance(native_attr_descr.type, collections.abc.Sequence):
                    if not isinstance(value, collections.abc.Sequence):
                        raise TypeError(f"{value!r} is not a sequence")
                    if len(value) != len(resource_attr_descrs):
                        raise ValueError(
                            f"{value!r} does not contain {len(resource_attr_descrs)} items"
                        )
                    return tuple(
                        self.converter.convert_to_attribute_value(
                            resource_attr_descr.type, resource_attr_descr.allow_null, v
                        )
                        for v, resource_attr_descr in zip(value, resource_attr_descrs)
                    )
                else:
                    raise TypeError("{value!r} is not convertible")
            except (ValueError, TypeError) as e:
                raise ConversionError(
                    ctx=ctx,
                    resource_attribute_descrs=resource_attr_descrs,
                    native_attribute_descrs=[native_attr_descr],
                ) from e

        return _

    def build_many_to_one_serde_converter(
        self,
        resource_attr_descr: ResourceAttributeDescriptor,
        native_attr_descrs: typing.Sequence[NativeAttributeDescriptor],
    ) -> typing.Callable[[ToSerdeContext, typing.Sequence[typing.Any]], AttributeValue]:
        def _(ctx: ToSerdeContext, value: typing.Sequence[typing.Any]) -> AttributeValue:
            try:
                if isinstance(resource_attr_descr.type, collections.abc.Sequence):
                    if not isinstance(value, collections.abc.Sequence):
                        raise TypeError(f"{value!r} is not a sequence")
                    if len(value) != len(native_attr_descrs):
                        raise ValueError(
                            f"{value!r} does not contain {len(native_attr_descrs)} items"
                        )
                    return tuple(
                        self.converter.convert_to_attribute_value(
                            native_attr_descr.type, resource_attr_descr.allow_null, v
                        )
                        for v, native_attr_descr in zip(value, native_attr_descrs)
                    )
                else:
                    raise TypeError("{value!r} is not convertible")
            except (ValueError, TypeError) as e:
                raise ConversionError(
                    ctx=ctx,
                    resource_attribute_descrs=[resource_attr_descr],
                    native_attribute_descrs=native_attr_descrs,
                ) from e

        return _

    def build_one_to_one_native_converter(
        self,
        native_attr_descr: NativeAttributeDescriptor,
        resource_attr_descr: ResourceAttributeDescriptor,
    ) -> typing.Callable[[ToNativeContext, Source, AttributeValue], typing.Any]:
        def _(ctx: ToNativeContext, source: Source, value: AttributeValue) -> typing.Any:
            if native_attr_descr.type is None:
                return None
            if native_attr_descr.allow_null and value is None:
                return None
            try:
                return self.converter.convert_from_attribute_value(native_attr_descr.type, value)
            except (ValueError, TypeError) as e:
                raise ConversionError(
                    ctx=ctx,
                    resource_attribute_descrs=[resource_attr_descr],
                    native_attribute_descrs=[native_attr_descr],
                    sources=[source],
                ) from e

        return _

    def build_one_to_many_native_converter(
        self,
        native_attr_descrs: typing.Sequence[NativeAttributeDescriptor],
        resource_attr_descr: ResourceAttributeDescriptor,
    ) -> typing.Callable[[ToNativeContext, Source, AttributeValue], typing.Sequence[typing.Any]]:
        def _(ctx: ToNativeContext, source: Source, value: AttributeValue) -> typing.Any:
            try:
                if isinstance(resource_attr_descr.type, collections.abc.Sequence):
                    if not isinstance(value, collections.abc.Sequence):
                        raise TypeError(f"{value!r} is not a sequence")
                    if len(value) != len(native_attr_descrs):
                        raise ValueError(
                            f"{value!r} does not contain {len(native_attr_descrs)} items"
                        )
                    return tuple(
                        self.converter.convert_from_attribute_value(native_attr_descr.type, v)
                        for v, native_attr_descr in zip(value, native_attr_descrs)
                    )
                else:
                    raise TypeError("{value!r} is not convertible")
            except (ValueError, TypeError):
                raise ConversionError(
                    ctx=ctx,
                    resource_attribute_descrs=[resource_attr_descr],
                    native_attribute_descrs=native_attr_descrs,
                    sources=[source],
                )

        return _

    def build_many_to_one_native_converter(
        self,
        native_attr_descr: NativeAttributeDescriptor,
        resource_attr_descrs: typing.Sequence[ResourceAttributeDescriptor],
    ) -> typing.Callable[
        [ToNativeContext, typing.Sequence[Source], typing.Sequence[AttributeValue]], typing.Any
    ]:
        def _(
            ctx: ToNativeContext,
            sources: typing.Sequence[Source],
            value: typing.Sequence[AttributeValue],
        ) -> typing.Any:
            if native_attr_descr.type is None:
                return None
            try:
                if isinstance(native_attr_descr.type, collections.abc.Mapping):
                    if not isinstance(value, collections.abc.Sequence):
                        raise TypeError(f"{value!r} is not a sequence")
                    if len(value) != len(resource_attr_descrs):
                        raise ValueError(
                            f"{value!r} does not contain {len(resource_attr_descrs)} items"
                        )
                    return {
                        resource_attr_descr.name: self.converter.convert_from_attribute_value(
                            resource_attr_descr.type, v
                        )
                        for v, resource_attr_descr in zip(value, resource_attr_descrs)
                    }
                elif isinstance(native_attr_descr.type, collections.abc.Sequence):
                    if not isinstance(value, collections.abc.Sequence):
                        raise TypeError(f"{value!r} is not a sequence")
                    if len(value) != len(resource_attr_descrs):
                        raise ValueError(
                            f"{value!r} does not contain {len(resource_attr_descrs)} items"
                        )
                    return tuple(
                        self.converter.convert_from_attribute_value(resource_attr_descr.type, v)
                        for v, resource_attr_descr in zip(value, resource_attr_descrs)
                    )
                else:
                    raise TypeError("{value!r} is not convertible")
            except (ValueError, TypeError):
                raise ConversionError(
                    ctx=ctx,
                    resource_attribute_descrs=resource_attr_descrs,
                    native_attribute_descrs=[native_attr_descr],
                    sources=sources,
                )

        return _

    def __init__(self, converter: BasicTypeConverter):
        self.converter = converter
