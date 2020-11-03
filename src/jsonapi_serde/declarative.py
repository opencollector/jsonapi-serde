import abc
import dataclasses
import typing

from .deferred import Deferred
from .interfaces import (
    NativeAttributeDescriptor,
    NativeDescriptor,
    NativeRelationshipDescriptor,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipDescriptor,
)
from .mapper import (
    AttributeMapping,
    ManyToOneAttributeMapping,
    Mapper,
    RelationshipMapping,
    ToManyAttributeMapping,
    ToNativeContext,
    ToOneAttributeMapping,
    ToSerdeContext,
)
from .models import (
    ResourceAttributeDescriptor,
    ResourceDescriptor,
    ResourceRelationshipDescriptor,
    ResourceToManyRelationshipDescriptor,
    ResourceToOneRelationshipDescriptor,
)
from .serde.models import AttributeValue, Source


class Members:
    members: typing.Sequence[str]

    def __init__(self, *members):
        self.members = members


class Dict(Members):
    pass


class Tuple(Members):
    pass


AttributeMappingType = typing.Sequence[
    typing.Tuple[typing.Union[str, Dict, Tuple], typing.Union[str, Dict, Tuple]]
]
RelatinoshipMappingType = typing.Sequence[typing.Tuple[str, str]]


@dataclasses.dataclass
class Meta:
    attribute_mappings: typing.Optional[AttributeMappingType] = None
    relationship_mappings: typing.Optional[RelatinoshipMappingType] = None


def handle_meta(meta: typing.Type) -> Meta:
    attrs = {k: v for k, v in vars(meta).items() if not k.startswith("__")}
    return Meta(
        attribute_mappings=attrs.get("attribute_mappings"),
        relationship_mappings=attrs.get("relationship_mappings"),
    )


class InfoExtractor(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def extract_descriptor_name_for_serde(self, native_descr: NativeDescriptor) -> str:
        ...  # pragma: nocover

    @abc.abstractmethod
    def extract_attribute_name_for_serde(self, native_attr_descr: NativeAttributeDescriptor) -> str:
        ...  # pragma: nocover

    @abc.abstractmethod
    def extract_attribute_type_for_serde(
        self, native_attr_descr: NativeAttributeDescriptor
    ) -> typing.Type:
        ...  # pragma: nocover

    @abc.abstractmethod
    def extract_attribute_nullability_for_serde(
        self, native_attr_descr: NativeAttributeDescriptor
    ) -> bool:
        ...  # pragma: nocover

    @abc.abstractmethod
    def extract_relationship_name_for_serde(
        self, native_rel_descr: NativeRelationshipDescriptor
    ) -> str:
        ...  # pragma: nocover


class ConverterFactory(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def build_one_to_one_serde_converter(
        self,
        resource_attr_descr: ResourceAttributeDescriptor,
        native_attr_descr: NativeAttributeDescriptor,
    ) -> typing.Callable[[ToSerdeContext, typing.Any], AttributeValue]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def build_one_to_many_serde_converter(
        self,
        resource_attr_descrs: typing.Sequence[ResourceAttributeDescriptor],
        native_attr_descr: NativeAttributeDescriptor,
    ) -> typing.Callable[[ToSerdeContext, typing.Any], typing.Sequence[AttributeValue]]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def build_many_to_one_serde_converter(
        self,
        resource_attr_descr: ResourceAttributeDescriptor,
        native_attr_descrs: typing.Sequence[NativeAttributeDescriptor],
    ) -> typing.Callable[[ToSerdeContext, typing.Sequence[typing.Any]], AttributeValue]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def build_one_to_one_native_converter(
        self,
        native_attr_descr: NativeAttributeDescriptor,
        resource_attr_descr: ResourceAttributeDescriptor,
    ) -> typing.Callable[[ToNativeContext, Source, AttributeValue], typing.Any]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def build_one_to_many_native_converter(
        self,
        native_attr_descrs: typing.Sequence[NativeAttributeDescriptor],
        resource_attr_descr: ResourceAttributeDescriptor,
    ) -> typing.Callable[[ToNativeContext, Source, AttributeValue], typing.Sequence[typing.Any]]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def build_many_to_one_native_converter(
        self,
        native_attr_descr: NativeAttributeDescriptor,
        resource_attr_descrs: typing.Sequence[ResourceAttributeDescriptor],
    ) -> typing.Callable[
        [ToNativeContext, typing.Sequence[Source], typing.Sequence[AttributeValue]], typing.Any
    ]:
        ...  # pragma: nocover


T = typing.TypeVar("T")


def assert_not_none(value: typing.Optional[T]) -> T:
    assert value is not None
    return value


def build_mapping(
    meta: Meta,
    native_descr: NativeDescriptor,
    info_extractor: InfoExtractor,
    query_mapper_by_native: typing.Callable[[NativeDescriptor], Mapper],
    converter_factory: ConverterFactory,
) -> typing.Tuple[
    ResourceDescriptor, typing.Sequence[AttributeMapping], typing.Sequence[RelationshipMapping]
]:
    resource_attrs: typing.List[ResourceAttributeDescriptor] = []
    resource_rels: typing.List[ResourceRelationshipDescriptor] = []
    attribute_mappings: typing.List[AttributeMapping] = []
    relationship_mappings: typing.List[RelationshipMapping] = []

    attribute_mappings_proto = meta.attribute_mappings
    if attribute_mappings_proto is None:
        for native_attr_descr in native_descr.attributes:
            resource_attr_descr = ResourceAttributeDescriptor(
                name=info_extractor.extract_attribute_name_for_serde(native_attr_descr),
                type=info_extractor.extract_attribute_type_for_serde(native_attr_descr),
                allow_null=info_extractor.extract_attribute_nullability_for_serde(
                    native_attr_descr
                ),
            )
            resource_attrs.append(resource_attr_descr)
            attribute_mappings.append(
                ToOneAttributeMapping(
                    resource_attr_descr,
                    native_attr_descr,
                    converter_factory.build_one_to_one_serde_converter(
                        resource_attr_descr, native_attr_descr
                    ),
                    converter_factory.build_one_to_one_native_converter(
                        native_attr_descr, resource_attr_descr
                    ),
                )
            )
    else:
        native_attr_descrs_map = {
            attr_descr.name: attr_descr for attr_descr in native_descr.attributes
        }
        for serde_side, native_side in attribute_mappings_proto:
            if isinstance(serde_side, str):
                if isinstance(native_side, str):
                    native_attr_descr = native_attr_descrs_map[native_side]
                    resource_attr_descr = ResourceAttributeDescriptor(
                        name=serde_side,
                        type=info_extractor.extract_attribute_type_for_serde(native_attr_descr),
                        allow_null=info_extractor.extract_attribute_nullability_for_serde(
                            native_attr_descr
                        ),
                    )
                    resource_attrs.append(resource_attr_descr)
                    attribute_mappings.append(
                        ToOneAttributeMapping(
                            resource_attr_descr,
                            native_attr_descr,
                            converter_factory.build_one_to_one_serde_converter(
                                resource_attr_descr, native_attr_descr
                            ),
                            converter_factory.build_one_to_one_native_converter(
                                native_attr_descr, resource_attr_descr
                            ),
                        )
                    )
                elif isinstance(native_side, Tuple):
                    native_attr_descrs = [native_attr_descrs_map[n] for n in native_side.members]
                    resource_attr_descr = ResourceAttributeDescriptor(
                        name=serde_side,
                        type=tuple,
                        allow_null=all(
                            info_extractor.extract_attribute_nullability_for_serde(
                                native_attr_descr
                            )
                            for native_attr_descr in native_attr_descrs
                        ),
                    )
                    resource_attrs.append(resource_attr_descr)
                    attribute_mappings.append(
                        ToManyAttributeMapping(
                            resource_attr_descr,
                            native_attr_descrs,
                            converter_factory.build_many_to_one_serde_converter(
                                resource_attr_descr, native_attr_descrs
                            ),
                            converter_factory.build_one_to_many_native_converter(
                                native_attr_descrs, resource_attr_descr
                            ),
                        )
                    )
                else:
                    raise AssertionError("should never get here!")
            elif isinstance(serde_side, Tuple):
                if isinstance(native_side, str):
                    native_attr_descr = native_attr_descrs_map[native_side]
                    allow_null = info_extractor.extract_attribute_nullability_for_serde(
                        native_attr_descr
                    )
                    resource_attr_descrs = [
                        ResourceAttributeDescriptor(
                            name=n,
                            type=assert_not_none(native_attr_descr.type),
                            allow_null=allow_null,
                        )
                        for n in serde_side.members
                    ]
                    resource_attrs.extend(resource_attr_descrs)
                    attribute_mappings.append(
                        ManyToOneAttributeMapping(
                            resource_attr_descrs,
                            native_attr_descr,
                            converter_factory.build_one_to_many_serde_converter(
                                resource_attr_descrs, native_attr_descr
                            ),
                            converter_factory.build_many_to_one_native_converter(
                                native_attr_descr, resource_attr_descrs
                            ),
                        )
                    )
                elif isinstance(native_side, Tuple):
                    raise NotImplementedError()
                elif isinstance(native_side, Dict):
                    raise NotImplementedError()
                else:
                    raise AssertionError("should never get here!")
            elif isinstance(serde_side, Dict):
                if isinstance(native_side, str):
                    native_attr_descr = native_attr_descrs_map[native_side]
                    allow_null = info_extractor.extract_attribute_nullability_for_serde(
                        native_attr_descr
                    )
                    resource_attr_descrs = [
                        ResourceAttributeDescriptor(
                            name=n,
                            type=assert_not_none(native_attr_descr.type),
                            allow_null=allow_null,
                        )
                        for n in serde_side.members
                    ]
                    resource_attrs.extend(resource_attr_descrs)
                    attribute_mappings.append(
                        ManyToOneAttributeMapping(
                            resource_attr_descrs,
                            native_attr_descr,
                            converter_factory.build_one_to_many_serde_converter(
                                resource_attr_descrs, native_attr_descr
                            ),
                            converter_factory.build_many_to_one_native_converter(
                                native_attr_descr, resource_attr_descrs
                            ),
                        )
                    )
                elif isinstance(native_side, Tuple):
                    raise NotImplementedError()
                elif isinstance(native_side, Dict):
                    raise NotImplementedError()
                else:
                    raise AssertionError("should never get here!")
            else:
                raise AssertionError("should never get here!")

    relationship_mappings_proto = meta.relationship_mappings
    resource_rel_descr: ResourceRelationshipDescriptor
    rel_mapping: RelationshipMapping
    if relationship_mappings_proto is None:
        for native_rel_descr in native_descr.relationships:
            name = native_rel_descr.name
            if name is None:
                continue
            dest_mapper = Deferred(lambda: query_mapper_by_native(native_rel_descr.destination))
            if isinstance(native_rel_descr, NativeToOneRelationshipDescriptor):
                resource_rel_descr = ResourceToOneRelationshipDescriptor(
                    dest_mapper.resource_descr,
                    name,
                )
                rel_mapping = RelationshipMapping(resource_rel_descr, native_rel_descr)
            elif isinstance(native_rel_descr, NativeToManyRelationshipDescriptor):
                resource_rel_descr = ResourceToManyRelationshipDescriptor(
                    dest_mapper.resource_descr,
                    name,
                )
                rel_mapping = RelationshipMapping(resource_rel_descr, native_rel_descr)
            else:
                raise AssertionError("should never get here!")
            resource_rels.append(resource_rel_descr)
            relationship_mappings.append(rel_mapping)
    else:
        native_rel_attr_descrs = {
            rel_descr.name: rel_descr for rel_descr in native_descr.relationships
        }
        for serde_side, native_side in relationship_mappings_proto:
            native_rel_descr = native_rel_attr_descrs[native_side]
            dest_mapper = Deferred(lambda: query_mapper_by_native(native_rel_descr.destination))
            if isinstance(native_rel_descr, NativeToOneRelationshipDescriptor):
                resource_rel_descr = ResourceToOneRelationshipDescriptor(
                    dest_mapper.resource_descr,
                    serde_side,
                )
                rel_mapping = RelationshipMapping(resource_rel_descr, native_rel_descr)
            elif isinstance(native_rel_descr, NativeToManyRelationshipDescriptor):
                resource_rel_descr = ResourceToManyRelationshipDescriptor(
                    dest_mapper.resource_descr,
                    serde_side,
                )
                rel_mapping = RelationshipMapping(resource_rel_descr, native_rel_descr)
            else:
                raise AssertionError("should never get here!")
            resource_rels.append(resource_rel_descr)
            relationship_mappings.append(rel_mapping)

    return (
        ResourceDescriptor(
            name=info_extractor.extract_descriptor_name_for_serde(native_descr),
            attributes=resource_attrs,
            relationships=resource_rels,
        ),
        attribute_mappings,
        relationship_mappings,
    )
