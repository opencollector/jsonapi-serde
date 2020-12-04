import enum
import typing


class RelationshipType(enum.Enum):
    TO_ONE = "to_one"
    TO_MANY = "to_many"


class ResourceAttributeDescriptor(typing.Protocol):
    name: str
    type: type
    allow_null: bool
    required_on_creation: bool


class ResourceRelationshipDescriptor(typing.Protocol):
    name: str
    destination: "ResourceDescriptor"
    type: RelationshipType


class ResourceDescriptor(typing.Protocol):
    name: str
    attributes: typing.Sequence[ResourceAttributeDescriptor]
    relationships: typing.Sequence[ResourceRelationshipDescriptor]
