import enum
import typing


class RelationshipType(enum.Enum):
    TO_ONE = "to_one"
    TO_MANY = "to_many"


class ResourceAttributeDescriptor(typing.Protocol):
    type: type
    name: str  # TODO
    allow_null: bool
    required_on_creation: bool
    read_only: bool
    write_only: bool


class ResourceRelationshipDescriptor(typing.Protocol):
    name: str
    destination: "ResourceDescriptor"
    type: RelationshipType


class ResourceDescriptor(typing.Protocol):
    name: str
    attributes: typing.Mapping[str, ResourceAttributeDescriptor]
    relationships: typing.Mapping[str, ResourceRelationshipDescriptor]
