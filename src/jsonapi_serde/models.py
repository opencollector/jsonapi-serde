import typing
from collections import OrderedDict

from .deferred import Deferred
from .exceptions import AttributeNotFoundError, RelationshipNotFoundError
from .serde.interfaces import RelationshipType
from .serde.models import AttributeValue, LinkageRepr, ResourceRepr, Source
from .utils import assert_not_none


class ResourceMemberDescriptor:
    parent: typing.Optional["ResourceDescriptor"] = None
    name: typing.Optional[str]

    T = typing.TypeVar("T", bound="ResourceMemberDescriptor")

    def bind(self: T, parent: "ResourceDescriptor") -> T:
        self.parent = parent
        return self

    def set_name(self: T, name: str) -> T:
        self.name = name
        return self


class ResourceAttributeDescriptor(ResourceMemberDescriptor):
    type: typing.Type[AttributeValue]
    allow_null: bool
    required_on_creation: bool
    read_only: bool
    write_only: bool

    def extract_value(
        self, repr_: ResourceRepr, source: typing.Optional[Source] = None
    ) -> AttributeValue:
        assert self.name is not None
        try:
            return repr_.attributes[self.name]
        except KeyError:
            assert self.parent is not None
            raise AttributeNotFoundError(self.parent, self.name, source)

    def __init__(
        self,
        type: typing.Type,
        name: typing.Optional[str] = None,
        allow_null: bool = False,
        required_on_creation: bool = True,
        read_only: bool = False,
        write_only: bool = False,
    ):
        self.name = name
        self.type = type
        self.allow_null = allow_null
        self.required_on_creation = required_on_creation
        self.read_only = read_only
        self.write_only = write_only


class ResourceRelationshipDescriptor(ResourceMemberDescriptor):
    _destination: typing.Union["ResourceDescriptor", Deferred["ResourceDescriptor"]]
    type: RelationshipType

    @property
    def destination(self) -> "ResourceDescriptor":
        if isinstance(self._destination, Deferred):
            return self._destination()
        else:
            return self._destination

    def extract_related(
        self, repr_: ResourceRepr, source: typing.Optional[Source] = None
    ) -> LinkageRepr:
        try:
            return repr_.relationships[assert_not_none(self.name)]
        except KeyError:
            assert self.parent is not None
            raise RelationshipNotFoundError(self.parent, assert_not_none(self.name), source)

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
        self.attributes = OrderedDict(
            ((assert_not_none(attr.name), attr.bind(self)) for attr in attributes)
        )
        self.relationships = OrderedDict(
            ((assert_not_none(rel.name), rel.bind(self)) for rel in relationships)
        )
