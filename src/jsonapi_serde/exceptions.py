import abc
import typing

from .serde.models import AttributeValue, Source
from .serde.utils import english_enumerate


class JSONAPISerdeException(Exception, metaclass=abc.ABCMeta):
    pass


class InvalidDeclarationError(JSONAPISerdeException):
    message: str

    def __init__(self, message):
        self.message = message


class JSONAPIMapperError(JSONAPISerdeException, metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def sources(self) -> typing.Sequence[Source]:
        ...


class JSONAPIAttributeError(JSONAPIMapperError):
    resource: "models.ResourceDescriptor"
    name: str
    _source: typing.Optional[Source]

    @property
    def sources(self) -> typing.Sequence[Source]:
        if self._source is None:
            return []
        else:
            return [self._source]

    @property
    @abc.abstractmethod
    def message(self) -> str:
        ...  # pragma: nocover

    def __init__(
        self,
        resource: "models.ResourceDescriptor",
        name: str,
        source: typing.Optional[Source] = None,
    ):
        self.resource = resource
        self.name = name
        self._source = source


class InvalidAttributeValueError(JSONAPIAttributeError):
    actual: AttributeValue
    detail: typing.Optional[str]

    @property
    def message(self):
        return f'attribute ({self.name}) in "{self.resource.name}" contains an invalid value{" (" + self.detail + ")" if self.detail is not None else ""}: {self.actual}'

    def __init__(
        self,
        resource: "models.ResourceDescriptor",
        name: str,
        actual: AttributeValue,
        detail: typing.Optional[str] = None,
        source: typing.Optional[Source] = None,
    ):
        super().__init__(resource, name, source)
        self.actual = actual
        self.detail = detail


class ImmutableAttributeError(JSONAPIAttributeError):
    @property
    def message(self):
        return f'attribute ({self.name}) in "{self.resource.name}" is immutable'


class AttributeNotFoundError(JSONAPIAttributeError):
    @property
    def message(self):
        return f'attribute ({self.name}) not supplied as specified in "{self.resource.name}"'


class RelationshipNotFoundError(JSONAPIMapperError):
    resource: "models.ResourceDescriptor"
    name: str
    _source: typing.Optional[Source]

    @property
    def sources(self) -> typing.Sequence[Source]:
        if self._source is None:
            return []
        else:
            return [self._source]

    @property
    def message(self):
        return f'relationship ({self.name}) not supplied as specified in "{self.resource.name}"'

    def __init__(
        self,
        resource: "models.ResourceDescriptor",
        name: str,
        source: typing.Optional[Source] = None,
    ):
        self.resource = resource
        self.name = name
        self._source = source


class UnknownResourceTypeError(JSONAPIMapperError):
    name: str
    _source: typing.Optional[Source]

    @property
    def sources(self) -> typing.Sequence[Source]:
        if self._source is None:
            return []
        else:
            return [self._source]

    @property
    def message(self):
        return f'no resource known as "{self.name}"'

    def __init__(self, name: str, source: typing.Optional[Source] = None):
        self.name = name
        self._source = source


class InvalidStructureError(JSONAPIMapperError):
    message: str

    @property
    def sources(self) -> typing.Sequence[Source]:
        return []

    def __init__(self, message: str):
        self.message = message


class GenericConstraintError(JSONAPIMapperError):
    message: str

    @property
    def sources(self) -> typing.Sequence[Source]:
        return []

    def __init__(self, message: str):
        self.message = message


class ConversionError(JSONAPIMapperError):
    ctx: typing.Union["mapper.ToSerdeContext", "mapper.ToNativeContext"]
    resource_attribute_descrs: typing.Sequence["models.ResourceAttributeDescriptor"]
    native_attribute_descrs: typing.Sequence["interfaces.NativeAttributeDescriptor"]
    _sources: typing.Sequence[Source]

    @property
    def sources(self) -> typing.Sequence[Source]:
        return self._sources

    @property
    def message(self):
        if isinstance(self.ctx, mapper.ToSerdeContext):
            source = english_enumerate(
                resource_attr_descr.name for resource_attr_descr in self.resource_attribute_descrs
            )
            return f"conversion from attribute {source} failed ({self.__cause__!s})"
        else:
            dest = english_enumerate(
                resource_attr_descr.name for resource_attr_descr in self.resource_attribute_descrs
            )
            return f"conversion to attributes {dest} failed ({self.__cause__!s})"

    def __str__(self):
        return self.message

    def __init__(
        self,
        ctx: typing.Union["mapper.ToSerdeContext", "mapper.ToNativeContext"],
        resource_attribute_descrs: typing.Sequence["models.ResourceAttributeDescriptor"],
        native_attribute_descrs: typing.Sequence["interfaces.NativeAttributeDescriptor"],
        sources: typing.Sequence[Source] = (),
    ):
        self.ctx = ctx
        self.resource_attribute_descrs = resource_attribute_descrs
        self.native_attribute_descrs = native_attribute_descrs
        self._sources = sources


class NativeError(JSONAPISerdeException):
    pass


class NativeResourceNotFoundError(NativeError):
    descr: "interfaces.NativeDescriptor"
    id: typing.Any

    @property
    def message(self):
        return f"no native resource {self.descr} found for {self.id}"

    def __init__(self, descr: "interfaces.NativeDescriptor", id: typing.Any):
        self.descr = descr
        self.id = id


class NativeAttributeNotFoundError(NativeError):
    descr: "interfaces.NativeDescriptor"
    name: str

    @property
    def message(self):
        return f"no such native attribute found in {self.descr}: {self.name}"

    def __init__(self, descr: "interfaces.NativeDescriptor", name: str):
        self.descr = descr
        self.name = name


class NativeRelationshipNotFoundError(NativeError):
    descr: "interfaces.NativeDescriptor"
    name: str

    @property
    def message(self):
        return f"no such native relationship found in {self.descr}: {self.name}"

    def __init__(self, descr: "interfaces.NativeDescriptor", name: str):
        self.descr = descr
        self.name = name


class InvalidNativeObjectStateError(NativeError):
    message: str

    def __init__(self, message: str):
        self.message = message


class InvalidIdentifierError(NativeError):
    message: str

    def __init__(self, message: str):
        self.message = message


from . import mapper  # noqa: E402

if typing.TYPE_CHECKING:
    from . import interfaces  # noqa: E402
    from . import models  # noqa: E402
