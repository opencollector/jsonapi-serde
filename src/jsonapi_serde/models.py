import typing

from .deferred import Deferred
from .serde.interfaces import RelationshipType
from .serde.models import AttributeValue, ResourceRepr


class ResourceMemberDescriptor:
    name: str


class ResourceAttributeDescriptor(ResourceMemberDescriptor):
    name: str
    type: typing.Type[AttributeValue]
    allow_null: bool

    def extract_value(self, repr_: ResourceRepr) -> AttributeValue:
        return repr_[self.name]

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

    def extract_related(self, repr_: ResourceRepr) -> typing.Any:
        for k, v in repr_.relationships:
            if k == self.name:
                return v
        raise KeyError(self.name)  # TODO: KeyError?

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
    attributes: typing.Sequence[ResourceAttributeDescriptor]
    relationships: typing.Sequence[ResourceRelationshipDescriptor]

    def __init__(
        self,
        name: str,
        attributes: typing.Iterable[ResourceAttributeDescriptor],
        relationships: typing.Iterable[ResourceRelationshipDescriptor],
    ):
        self.name = name
        self.attributes = list(attributes)
        self.relationships = list(relationships)
