import typing
from collections import OrderedDict

from .deferred import Deferred
from .exceptions import AttributeNotFoundError, RelationshipNotFoundError
from .serde.interfaces import RelationshipType
from .serde.models import AttributeValue, ResourceRepr, Source


class ResourceMemberDescriptor:
    parent: typing.Optional["ResourceDescriptor"] = None
    name: str

    T = typing.TypeVar("T", bound="ResourceMemberDescriptor")

    def bind(self: T, parent: ResourceDescriptor) -> T:
        self.parent = parent
        return self


class ResourceAttributeDescriptor(ResourceMemberDescriptor):
    name: str
    type: typing.Type[AttributeValue]
    allow_null: bool

    def extract_value(self, repr_: ResourceRepr, source: typing.Optional[Source] = None) -> AttributeValue:
        try:
            return repr_.attributes[self.name]
        except KeyError:
            assert self.parent is not None
            raise AttributeNotFoundError(self.parent, self.name, source)

    def __init__(
        self,
        name: str,
        type: typing.Type,
        allow_null: bool,
    ):
        self.name = name
        self.type = type
        self.allow_null = allow_null


class ResourceRelationshipDescriptor(ResourceMemberDescriptor):
    _destination: typing.Union["ResourceDescriptor", Deferred["ResourceDescriptor"]]
    name: str
    type: RelationshipType

    @property
    def destination(self) -> "ResourceDescriptor":
        if isinstance(self._destination, Deferred):
            return self._destination()
        else:
            return self._destination

    def extract_related(self, repr_: ResourceRepr, source: typing.Optional[Source] = None) -> LinkageRepr:
        try:
            return repr_.relationships[self.name]
        except KeyError:
            assert self.parent is not None
            raise RelationshipNotFoundError(self.parent, self.name, source)

    def __init__(
        self,
        destination: typing.Union["ResourceDescriptor", Deferred["ResourceDescriptor"]],
        name: str,
    ):
        super().__init__()
        self._destination = destination
        self.name = name


class ResourceToOneRelationshipDescriptor(ResourceRelationshipDescriptor):
    type = RelationshipType.TO_ONE


class ResourceToManyRelationshipDescriptor(ResourceRelationshipDescriptor):
    type = RelationshipType.TO_MANY


class ResourceDescriptor:
    name: str
    attributes: typing.Mapping[str, ResourceAttributeDescriptor]
    relationships: typing.Mapping[str, ResourceRelationshipDescriptor]

    def __init__(
        self,
        name: str,
        attributes: typing.Iterable[ResourceAttributeDescriptor],
        relationships: typing.Iterable[ResourceRelationshipDescriptor],
    ):
        self.name = name
        self.attributes = OrderedDict((
            (attribute.name, attr.bind(attribute))
            for attr in attributes
        ))
        self.relationships = OrderedDict((
            (rel.name, rel.bind(rel))
            for rel in relationships
        ))
