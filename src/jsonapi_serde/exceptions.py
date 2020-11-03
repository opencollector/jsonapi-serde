import abc
import typing

from .serde.models import Source
from .serde.utils import english_enumerate


class JSONAPIMapperError(Exception, metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def sources(self) -> typing.Sequence[Source]:
        ...


class AttributeNotFoundError(JSONAPIMapperError):
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
        return f'no such attribute ({self.name}) not found in "{self.resource.name}"'

    def __init__(
        self,
        resource: "models.ResourceDescriptor",
        name: str,
        source: typing.Optional[Source] = None,
    ):
        self.resource = resource
        self.name = name
        self._source = source


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
        return f'no such relationship ({self.name}) not found in "{self.resource.name}"'

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


class InvalidIdentifierError(JSONAPIMapperError):
    message: str
    _source: typing.Optional[Source]

    @property
    def sources(self) -> typing.Sequence[Source]:
        if self._source is None:
            return []
        else:
            return [self._source]

    def __init__(self, message: str, source: typing.Optional[Source] = None):
        self.message = message
        self._source = source


class InvalidNativeObjectStateError(JSONAPIMapperError):
    message: str

    @property
    def sources(self) -> typing.Sequence[Source]:
        return []

    def __init__(self, message: str):
        self.message = message


class NativeResourceNotFoundError(JSONAPIMapperError):
    descr: "interfaces.NativeDescriptor"
    id: typing.Any

    @property
    def sources(self) -> typing.Sequence[Source]:
        return []

    @property
    def message(self):
        return f"no native resource {self.descr} found for {self.id}"

    def __init__(self, descr: "interfaces.NativeDescriptor", id: typing.Any):
        self.descr = descr
        self.id = id


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


from . import mapper  # noqa: E402

if typing.TYPE_CHECKING:
    from . import interfaces  # noqa: E402
    from . import models  # noqa: E402
