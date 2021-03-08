import typing
from collections import OrderedDict

from .deferred import Deferred
from .serde.interfaces import RelationshipType
from .serde.models import AttributeValue, LinkageRepr, ResourceRepr, Source
from .utils import assert_not_none


class ResourceMemberDescriptor:
    parent: typing.Optional["ResourceDescriptor"] = None
    name: str

    T = typing.TypeVar("T", bound="ResourceMemberDescriptor")

    def bind(self: T, parent: "ResourceDescriptor") -> T:
        self.parent = parent
        return self


class ResourceAttributeDescriptor(ResourceMemberDescriptor):
    type: typing.Type[AttributeValue]
    allow_null: bool
    required_on_creation: bool
    read_only: bool
    write_only: bool
    immutable: bool

    def extract_value(
        self, repr_: ResourceRepr, source: typing.Optional[Source] = None
    ) -> AttributeValue:
        from .exceptions import AttributeNotFoundError

        assert self.name is not None
        try:
            return repr_.attributes[self.name]
        except KeyError:
            assert self.parent is not None
            raise AttributeNotFoundError(self.parent, self.name, source)

    def __init__(
        self,
        type: typing.Type,
        name: str,
        allow_null: bool = False,
        required_on_creation: bool = True,
        read_only: bool = False,
        write_only: bool = False,
        immutable: bool = False,
    ):
        self.name = name
        self.type = type
        self.allow_null = allow_null
        self.required_on_creation = required_on_creation
        self.read_only = read_only
        self.write_only = write_only
        self.immutable = immutable


class ResourceRelationshipDescriptor(ResourceMemberDescriptor):
    _destination: typing.Union["ResourceDescriptor", Deferred["ResourceDescriptor"]]
    type: RelationshipType
    required_on_creation: bool
    read_only: bool
    write_only: bool
    immutable: bool

    @property
    def destination(self) -> "ResourceDescriptor":
        if isinstance(self._destination, Deferred):
            return self._destination()
        else:
            return self._destination

    def extract_related(
        self, repr_: ResourceRepr, source: typing.Optional[Source] = None
    ) -> LinkageRepr:
        from .exceptions import RelationshipNotFoundError

        try:
            return repr_.relationships[assert_not_none(self.name)]
        except KeyError:
            assert self.parent is not None
            raise RelationshipNotFoundError(self.parent, assert_not_none(self.name), source)

    def __init__(
        self,
        destination: typing.Union["ResourceDescriptor", Deferred["ResourceDescriptor"]],
        name: str,
        required_on_creation: bool = False,
        read_only: bool = False,
        write_only: bool = False,
        immutable: bool = False,
    ):
        super().__init__()
        self._destination = destination
        self.name = name
        self.required_on_creation = required_on_creation
        self.read_only = read_only
        self.write_only = write_only
        self.immutable = immutable


class ResourceToOneRelationshipDescriptor(ResourceRelationshipDescriptor):
    type = RelationshipType.TO_ONE
    allow_null: bool

    def __init__(
        self,
        destination: typing.Union["ResourceDescriptor", Deferred["ResourceDescriptor"]],
        name: str,
        required_on_creation: bool = False,
        read_only: bool = False,
        write_only: bool = False,
        immutable: bool = False,
        allow_null: bool = False,
    ):
        super().__init__(destination, name, required_on_creation, read_only, write_only, immutable)
        self.allow_null = allow_null


class ResourceToManyRelationshipDescriptor(ResourceRelationshipDescriptor):
    type = RelationshipType.TO_MANY
    allow_empty: bool

    def __init__(
        self,
        destination: typing.Union["ResourceDescriptor", Deferred["ResourceDescriptor"]],
        name: str,
        required_on_creation: bool = False,
        read_only: bool = False,
        write_only: bool = False,
        immutable: bool = False,
        allow_empty: bool = True,
    ):
        super().__init__(destination, name, required_on_creation, read_only, write_only, immutable)
        self.allow_empty = allow_empty


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
