import collections.abc
import json
import math
import typing

from .exceptions import DeserializationError
from .interfaces import ResourceDescriptor
from .models import (
    URL,
    AttributeValue,
    DocumentReprBase,
    LinkageRepr,
    LinksRepr,
    Repr,
    ResourceRepr,
)
from .types import JSONObject, JSONValue
from .utils.converter import (
    ConverterContext,
    CustomConverterFuncAdapter,
    ErrorCollectingConverterContext,
    JsonicDataValidationError,
    JsonicType,
    JsonicValue,
    NameMapperFuncAdapter,
    PyTypedJsonicDataConverter,
)
from .utils.jsonpointer import JSONPointer


class DescriptorQuerier(typing.Protocol):
    def __call__(self, name: str) -> ResourceDescriptor:
        ...  # pragma: nocover


class OurErrorCollectingConverterContext(ErrorCollectingConverterContext):
    require_complete_set_of_attributes: bool

    def __init__(self, require_complete_set_of_attributes: bool):
        super().__init__()
        self.require_complete_set_of_attributes = require_complete_set_of_attributes


EMPTY_ATTRIBUTES_DICT: typing.Mapping[str, JSONValue] = {}


class ReprDeserializer:
    _converter: PyTypedJsonicDataConverter
    _querier: typing.Optional[DescriptorQuerier]

    def _convert_resource_repr(
        self,
        converter: PyTypedJsonicDataConverter,
        ctx: ConverterContext,
        pointer: JSONPointer,
        typ: JsonicType,
        value: JSONValue,
    ) -> typing.Tuple[JsonicValue, float]:
        if not isinstance(value, collections.abc.Mapping):
            ctx.validation_error_occurred(
                JsonicDataValidationError(
                    pointer,
                    f"value has type {converter.py_type_repr(type(value))} ({json.dumps(value)}) where {converter.type_repr(typ)} expected",
                )
            )
            return (None, math.inf)
        try:
            type_ = value["type"]
            attributes_ = value.get("attributes", EMPTY_ATTRIBUTES_DICT)
            attributes: typing.MutableSequence[typing.Tuple[str, AttributeValue]] = []
            v: JSONValue
            _pointer = pointer / "attributes"
            if self._querier is None:
                for k, v in attributes_.items():
                    attributes.append(
                        (
                            k,
                            typing.cast(
                                AttributeValue,
                                converter._convert(ctx, _pointer / k, AttributeValue, v)[0],
                            ),
                        )
                    )
                    if ctx.stopped:
                        break
                    else:
                        continue
            else:
                attributes = []
                try:
                    resource_descr = self._querier(type_)
                except Exception:
                    ctx.validation_error_occurred(
                        JsonicDataValidationError(
                            pointer,
                            f'unknown resource type "{type_}"',
                        )
                    )
                    return (None, math.inf)

                attr_names = set(attributes_.keys())
                for attr_descr in resource_descr.attributes.values():
                    if attr_descr.name not in attributes_:
                        if (
                            not typing.cast(
                                OurErrorCollectingConverterContext, ctx
                            ).require_complete_set_of_attributes
                            or not attr_descr.required_on_creation
                            or attr_descr.read_only
                        ):
                            continue

                        ctx.validation_error_occurred(
                            JsonicDataValidationError(
                                pointer,
                                f'attribute "{attr_descr.name}" is not provided where a complete set of attributes is wanted',
                            )
                        )
                        if ctx.stopped:
                            break
                        else:
                            continue
                    else:
                        v = attributes_[attr_descr.name]
                        attr_names.remove(attr_descr.name)
                    attributes.append(
                        (
                            attr_descr.name,
                            typing.cast(
                                AttributeValue,
                                converter._convert(
                                    ctx,
                                    _pointer / attr_descr.name,
                                    (
                                        typing.Optional[attr_descr.type]
                                        if attr_descr.allow_null
                                        else attr_descr.type
                                    ),
                                    v,
                                )[0],
                            ),
                        )
                    )
                    if ctx.stopped:
                        break
                    else:
                        continue

                if attr_names:
                    for name in attr_names:
                        ctx.validation_error_occurred(
                            JsonicDataValidationError(
                                pointer / name,
                                f'unknown attribute "{name}"',
                            )
                        )

            relationships: typing.Sequence[typing.Tuple[str, LinkageRepr]] = ()

            if "relationships" in value:
                relationships = tuple(
                    (
                        k,
                        typing.cast(
                            LinkageRepr,
                            converter._convert(ctx, pointer / "relationships" / k, LinkageRepr, v)[
                                0
                            ],
                        ),
                    )
                    for k, v in value["relationships"].items()
                )

            id_: typing.Optional[str] = None
            id_repr = value.get("id")
            if id_repr is not None:
                id_ = typing.cast(str, converter._convert(ctx, pointer / "id", str, value["id"])[0])

            return (
                ResourceRepr(
                    type=typing.cast(str, converter._convert(ctx, pointer / "type", str, type_)[0]),
                    id=id_,
                    attributes=attributes,
                    relationships=relationships,
                ),
                1.0,
            )
        except KeyError as e:
            ctx.validation_error_occurred(
                JsonicDataValidationError(
                    pointer / e.args[0], f'value must have a property "{e.args[0]}"'
                )
            )
            return (None, math.inf)

    def _convert_url(
        self,
        converter: PyTypedJsonicDataConverter,
        ctx: ConverterContext,
        pointer: JSONPointer,
        typ: JsonicType,
        value: JSONValue,
    ) -> typing.Tuple[JsonicValue, float]:
        if not isinstance(value, str):
            ctx.validation_error_occurred(
                JsonicDataValidationError(pointer, f"value must have be string, got {value!r}")
            )
            return (None, math.inf)

        try:
            return (URL.from_string(value), 1.0)
        except ValueError:
            ctx.validation_error_occurred(
                JsonicDataValidationError(pointer, f"failed to parse {value!r} as a URL")
            )
            return (None, math.inf)

    def _set_source(
        self,
        converter: "PyTypedJsonicDataConverter",
        ctx: "ConverterContext",
        pointer: JSONPointer,
        typ: JsonicType,
        value: JsonicValue,
    ) -> JsonicValue:
        if isinstance(value, Repr):
            value._source_ = pointer
        return value

    T = typing.TypeVar("T", bound=DocumentReprBase)

    def __call__(
        self,
        result_type: typing.Type[T],
        document: JSONObject,
        require_complete_set_of_attributes: bool = False,
    ) -> T:
        ctx = OurErrorCollectingConverterContext(require_complete_set_of_attributes)
        retval = self._converter.convert(ctx, result_type, document)
        if ctx.errors:
            raise DeserializationError(document, ctx.errors)
        return retval

    def __init__(self, querier: typing.Optional[DescriptorQuerier] = None):
        default_name_mapper_func = NameMapperFuncAdapter(
            lambda c, p, t, k: k,
            lambda c, p, t, k: None if k == "_source_" else k,
        )
        self._converter = PyTypedJsonicDataConverter(
            {
                ResourceRepr: CustomConverterFuncAdapter(
                    lambda typ: "resource",
                    self._convert_resource_repr,
                ),
                URL: CustomConverterFuncAdapter(
                    lambda typ: "URL",
                    self._convert_url,
                ),
            },
            {
                LinksRepr: NameMapperFuncAdapter(
                    lambda c, p, t, k: (
                        "self_" if k == "self" else default_name_mapper_func.resolve(c, p, t, k)
                    ),
                    lambda c, p, t, k: (
                        "self"
                        if k == "self_"
                        else default_name_mapper_func.reverse_resolve(c, p, t, k)
                    ),
                ),
                typing.Any: default_name_mapper_func,
            },
            self._set_source,
        )
        self._querier = querier
