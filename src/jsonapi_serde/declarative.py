import abc
import collections.abc
import dataclasses
import enum
import typing

from .deferred import Deferred
from .exceptions import InvalidDeclarationError
from .interfaces import (
    MutationContext,
    NativeAttributeDescriptor,
    NativeBuilder,
    NativeDescriptor,
    NativeRelationshipDescriptor,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipDescriptor,
)
from .mapper import (
    AttributeMapping,
    Direction,
    ManyToOneAttributeMapping,
    Mapper,
    RelationshipMapping,
    SerdeBuilderContext,
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
from .serde.builders import ResourceIdReprBuilder, ResourceReprBuilder
from .serde.models import AttributeValue, ResourceRepr, Source
from .utils import assert_not_none


class Members:
    members: typing.Sequence[typing.Union[str, ResourceAttributeDescriptor]]
    member_type: typing.Union[typing.Type[str], typing.Type[ResourceAttributeDescriptor]]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(repr(m) for m in self.members)})"

    def __iter__(self):
        return iter(self.members)

    def __init__(self, *members):
        member_types = set(type(m) for m in self.members)
        if len(member_types) != 1:
            raise TypeError("members are not homogenious")
        member_type = member_types.pop()
        if member_type not in (str, ResourceAttributeDescriptor):
            raise TypeError("every member must be either a str or ResourceAttributeDescriptor")
        self.members = members
        self.member_type = member_type


class Dict(Members):
    pass


class Tuple(Members):
    pass


AttributeMappingSerdeSide = typing.Union[str, ResourceAttributeDescriptor, Dict, Tuple]
AttributeMappingNativeSide = typing.Union[str, Dict, Tuple]


Bidi = typing.Tuple[AttributeMappingSerdeSide, AttributeMappingNativeSide]


class ReadOnly(typing.Tuple[AttributeMappingSerdeSide, AttributeMappingNativeSide]):
    def __new__(cls, *args):
        return super(ReadOnly, cls).__new__(cls, args)


class WriteOnly(typing.Tuple[AttributeMappingSerdeSide, AttributeMappingNativeSide]):
    def __new__(cls, *args):
        return super(WriteOnly, cls).__new__(cls, args)


AttributeMappingType = typing.Sequence[
    typing.Union[
        Bidi,
        ReadOnly,
        WriteOnly,
    ]
]
RelationshipMappingType = typing.Sequence[typing.Tuple[str, str]]


@dataclasses.dataclass
class SerdeSideMeta:
    attributes: typing.Sequence[ResourceAttributeDescriptor] = ()
    attribute_overrides: typing.Mapping[str, ResourceAttributeDescriptor] = dataclasses.field(
        default_factory=dict
    )
    resource_filters: typing.Sequence[
        typing.Callable[[ToNativeContext, Mapper, ResourceRepr], ResourceRepr]
    ] = ()
    builder_filters: typing.Sequence[
        typing.Callable[
            [ToNativeContext, Mapper, MutationContext, ResourceRepr, NativeBuilder], NativeBuilder
        ]
    ] = ()
    native_filters: typing.Sequence[
        typing.Callable[
            [ToNativeContext, Mapper, MutationContext, ResourceRepr, typing.Any], typing.Any
        ]
    ] = ()


@dataclasses.dataclass
class NativeSideMeta:
    builder_filters: typing.Sequence[
        typing.Callable[
            [
                ToSerdeContext,
                Mapper,
                SerdeBuilderContext,
                typing.Union[ResourceReprBuilder, ResourceIdReprBuilder],
            ],
            typing.Union[ResourceReprBuilder, ResourceIdReprBuilder],
        ]
    ] = ()


@dataclasses.dataclass
class Meta:
    attribute_mappings: typing.Optional[AttributeMappingType] = None
    relationship_mappings: typing.Optional[RelationshipMappingType] = None
    serde_side: SerdeSideMeta = dataclasses.field(default_factory=SerdeSideMeta)
    native_side: NativeSideMeta = dataclasses.field(default_factory=NativeSideMeta)


def handle_meta(meta: typing.Type) -> Meta:
    attrs = {k: v for k, v in vars(meta).items() if not k.startswith("__")}
    serde_side = attrs.get("serde_side", {})
    if "attributes" in serde_side:
        attributes: typing.Sequence[ResourceAttributeDescriptor]
        _attributes = typing.cast(
            typing.Union[
                typing.Sequence[ResourceAttributeDescriptor],
                typing.Mapping[str, ResourceAttributeDescriptor],
            ],
            serde_side["attributes"],
        )
        if isinstance(_attributes, collections.abc.Mapping):
            attributes = [attr.set_name(name) for name, attr in _attributes.items()]
        else:
            assert isinstance(_attributes, collections.abc.Sequence)
            attributes = _attributes
        serde_side["attributes"] = attributes
    return Meta(
        attribute_mappings=attrs.get("attribute_mappings"),
        relationship_mappings=attrs.get("relationship_mappings"),
        serde_side=SerdeSideMeta(**serde_side),
        native_side=NativeSideMeta(**attrs.get("native_side", {})),
    )


class AttributeFlags(enum.IntFlag):
    NONE = 0
    ALLOW_NULL = 1
    REQUIRED_ON_CREATION = 2
    READ_ONLY = 4
    WRITE_ONLY = 8


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
    def extract_attribute_flags_for_serde(
        self, native_attr_descr: NativeAttributeDescriptor
    ) -> AttributeFlags:
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


class MapperBuilder:
    info_extractor: InfoExtractor
    query_mapper_by_native: typing.Callable[[NativeDescriptor], Mapper]
    converter_factory: ConverterFactory

    def build_attribute_mapping_auto(
        self,
        native_descr: NativeDescriptor,
        predefined_resource_attrs: typing.Optional[
            typing.Mapping[str, ResourceAttributeDescriptor]
        ],
        resource_attr_overrides: typing.Mapping[str, ResourceAttributeDescriptor],
    ) -> typing.Tuple[
        typing.Sequence[ResourceAttributeDescriptor], typing.Sequence[AttributeMapping]
    ]:
        resource_attrs: typing.List[ResourceAttributeDescriptor] = []
        attribute_mappings: typing.List[AttributeMapping] = []

        for native_attr_descr in native_descr.attributes:
            flag = self.info_extractor.extract_attribute_flags_for_serde(native_attr_descr)
            name = self.info_extractor.extract_attribute_name_for_serde(native_attr_descr)

            resource_attr_descr: ResourceAttributeDescriptor
            if name in resource_attr_overrides:
                resource_attr_descr = resource_attr_overrides[name]
            elif predefined_resource_attrs is not None:
                if name not in predefined_resource_attrs:
                    raise InvalidDeclarationError(
                        f"descriptor for attribute {name} must exist in serde_side.attributes"
                    )
                resource_attr_descr = predefined_resource_attrs[name]
            else:
                resource_attr_descr = ResourceAttributeDescriptor(
                    type=self.info_extractor.extract_attribute_type_for_serde(native_attr_descr),
                    name=name,
                    allow_null=bool(flag & AttributeFlags.ALLOW_NULL),
                    required_on_creation=bool(flag & AttributeFlags.REQUIRED_ON_CREATION),
                    read_only=bool(flag & AttributeFlags.READ_ONLY),
                    write_only=bool(flag & AttributeFlags.WRITE_ONLY),
                )
            resource_attrs.append(resource_attr_descr)
            attribute_mappings.append(
                ToOneAttributeMapping(
                    serde_side=resource_attr_descr,
                    native_side=native_attr_descr,
                    to_serde_factory=self.converter_factory.build_one_to_one_serde_converter(
                        resource_attr_descr, native_attr_descr
                    ),
                    to_native_factory=self.converter_factory.build_one_to_one_native_converter(
                        native_attr_descr, resource_attr_descr
                    ),
                    direction=(
                        Direction.TO_SERDE_ONLY if resource_attr_descr.read_only else Direction.BIDI
                    ),
                )
            )
        return resource_attrs, attribute_mappings

    def build_attribute_mapping_from_proto(
        self,
        native_descr: NativeDescriptor,
        predefined_resource_attrs: typing.Optional[
            typing.Mapping[str, ResourceAttributeDescriptor]
        ],
        resource_attr_overrides: typing.Mapping[str, ResourceAttributeDescriptor],
        attribute_mappings_proto: AttributeMappingType,
    ) -> typing.Tuple[
        typing.Sequence[ResourceAttributeDescriptor], typing.Sequence[AttributeMapping]
    ]:
        resource_attrs: typing.List[ResourceAttributeDescriptor] = []
        attribute_mappings: typing.List[AttributeMapping] = []

        native_attr_descrs_map = {
            attr_descr.name: attr_descr for attr_descr in native_descr.attributes
        }

        for pair in attribute_mappings_proto:
            direction = Direction.BIDI

            if isinstance(pair, ReadOnly):
                direction = Direction.TO_SERDE_ONLY
            elif isinstance(pair, WriteOnly):
                direction = Direction.TO_NATIVE_ONLY

            serde_side, native_side = pair

            if isinstance(serde_side, (str, ResourceAttributeDescriptor)):
                resource_attr_descr: typing.Optional[ResourceAttributeDescriptor] = None
                serde_side_name: typing.Optional[str] = None

                if predefined_resource_attrs is not None:
                    if not isinstance(serde_side, str):
                        raise InvalidDeclarationError(
                            "resource descriptors are provided in serde_side"
                        )
                    resource_attr_descr = predefined_resource_attrs[serde_side]
                else:
                    if isinstance(serde_side, str):
                        if serde_side in resource_attr_overrides:
                            resource_attr_descr = resource_attr_overrides[serde_side]
                        else:
                            serde_side_name = serde_side
                    else:
                        resource_attr_descr = serde_side

                if isinstance(native_side, str):
                    if resource_attr_descr is None:
                        native_attr_descr = native_attr_descrs_map[native_side]
                        flag = self.info_extractor.extract_attribute_flags_for_serde(
                            native_attr_descr
                        )
                        if serde_side_name is None:
                            serde_side_name = self.info_extractor.extract_attribute_name_for_serde(
                                native_attr_descr
                            )
                        resource_attr_descr = ResourceAttributeDescriptor(
                            type=self.info_extractor.extract_attribute_type_for_serde(
                                native_attr_descr
                            ),
                            name=serde_side_name,
                            allow_null=bool(flag & AttributeFlags.ALLOW_NULL),
                            required_on_creation=bool(flag & AttributeFlags.REQUIRED_ON_CREATION),
                            read_only=direction is Direction.TO_SERDE_ONLY,
                            write_only=direction is Direction.TO_NATIVE_ONLY,
                        )
                    else:
                        if resource_attr_descr.name is None:
                            resource_attr_descr.name = (
                                self.info_extractor.extract_attribute_name_for_serde(
                                    native_attr_descr
                                )
                            )
                        resource_attr_descr.read_only = direction is Direction.TO_SERDE_ONLY  # TODO
                        resource_attr_descr.write_only = (
                            direction is Direction.TO_NATIVE_ONLY
                        )  # TODO

                    resource_attrs.append(resource_attr_descr)
                    attribute_mappings.append(
                        ToOneAttributeMapping(
                            resource_attr_descr,
                            native_attr_descr,
                            self.converter_factory.build_one_to_one_serde_converter(
                                resource_attr_descr, native_attr_descr
                            ),
                            self.converter_factory.build_one_to_one_native_converter(
                                native_attr_descr, resource_attr_descr
                            ),
                            direction=direction,
                        )
                    )
                elif isinstance(native_side, Tuple):
                    native_attr_descrs = [
                        native_attr_descrs_map[typing.cast(str, n)] for n in native_side.members
                    ]
                    if resource_attr_descr is None:
                        flags = [
                            self.info_extractor.extract_attribute_flags_for_serde(native_attr_descr)
                            for native_attr_descr in native_attr_descrs
                        ]
                        resource_attr_descr = ResourceAttributeDescriptor(
                            type=tuple,
                            name=serde_side_name,
                            allow_null=all(bool(f & AttributeFlags.ALLOW_NULL) for f in flags),
                            required_on_creation=any(
                                bool(f & AttributeFlags.REQUIRED_ON_CREATION) for f in flags
                            ),
                            read_only=direction is Direction.TO_SERDE_ONLY,
                            write_only=direction is Direction.TO_NATIVE_ONLY,
                        )
                    else:
                        if resource_attr_descr.name is None:
                            raise InvalidDeclarationError(
                                "resource descriptor does not have name specified"
                            )
                        resource_attr_descr.read_only = direction is Direction.TO_SERDE_ONLY  # TODO
                        resource_attr_descr.write_only = (
                            direction is Direction.TO_NATIVE_ONLY
                        )  # TODO

                    resource_attrs.append(resource_attr_descr)
                    attribute_mappings.append(
                        ToManyAttributeMapping(
                            resource_attr_descr,
                            native_attr_descrs,
                            self.converter_factory.build_many_to_one_serde_converter(
                                resource_attr_descr, native_attr_descrs
                            ),
                            self.converter_factory.build_one_to_many_native_converter(
                                native_attr_descrs, resource_attr_descr
                            ),
                            direction=direction,
                        )
                    )
                else:
                    raise InvalidDeclarationError("invalid mapping: {serde_side} : {native_side}")
            elif isinstance(serde_side, (Tuple, Dict)):
                if isinstance(native_side, str):
                    native_attr_descr = native_attr_descrs_map[native_side]
                    resource_attr_descrs: typing.Sequence[ResourceAttributeDescriptor]
                    if serde_side.member_type is str:
                        flag = self.info_extractor.extract_attribute_flags_for_serde(
                            native_attr_descr
                        )
                        allow_null = bool(flag & AttributeFlags.ALLOW_NULL)
                        required_on_creation = bool(flag & AttributeFlags.REQUIRED_ON_CREATION)
                        resource_attr_descrs = []
                        for n in serde_side.members:
                            n = typing.cast(str, n)
                            if predefined_resource_attrs:
                                resource_attr_descr = predefined_resource_attrs[n]
                            else:
                                if n in resource_attr_overrides:
                                    resource_attr_descr = resource_attr_overrides[n]
                                else:
                                    resource_attr_descr = ResourceAttributeDescriptor(
                                        type=str,
                                        name=n,
                                        allow_null=allow_null,
                                        required_on_creation=required_on_creation,
                                        read_only=direction is Direction.TO_SERDE_ONLY,
                                        write_only=direction is Direction.TO_NATIVE_ONLY,
                                    )
                            resource_attr_descrs.append(resource_attr_descr)
                    else:
                        if not all(
                            typing.cast(ResourceAttributeDescriptor, i).name is not None
                            for i in serde_side.members
                        ):
                            raise InvalidDeclarationError(
                                "serde side of a mapping contains an unnamed ResourceAttributeDescriptor"
                            )
                        for resource_attr_descr in resource_attr_descrs:
                            resource_attr_descr.read_only = (
                                direction is Direction.TO_SERDE_ONLY
                            )  # TODO
                            resource_attr_descr.write_only = (
                                direction is Direction.TO_NATIVE_ONLY
                            )  # TODO
                        resource_attr_descrs = typing.cast(
                            typing.Sequence[ResourceAttributeDescriptor], serde_side.members
                        )

                    resource_attrs.extend(resource_attr_descrs)
                    attribute_mappings.append(
                        ManyToOneAttributeMapping(
                            resource_attr_descrs,
                            native_attr_descr,
                            self.converter_factory.build_one_to_many_serde_converter(
                                resource_attr_descrs, native_attr_descr
                            ),
                            self.converter_factory.build_many_to_one_native_converter(
                                native_attr_descr, resource_attr_descrs
                            ),
                            direction=direction,
                        )
                    )
                else:
                    raise InvalidDeclarationError("invalid mapping: {serde_side} : {native_side}")
            else:
                raise InvalidDeclarationError("invalid mapping: {serde_side} : {native_side}")
        return resource_attrs, attribute_mappings

    def build_relationship_mapping_auto(
        self,
        native_descr: NativeDescriptor,
    ) -> typing.Tuple[
        typing.Sequence[ResourceRelationshipDescriptor],
        typing.Sequence[RelationshipMapping],
    ]:
        resource_rels: typing.List[ResourceRelationshipDescriptor] = []
        relationship_mappings: typing.List[RelationshipMapping] = []

        for native_rel_descr in native_descr.relationships:
            resource_rel_descr: ResourceRelationshipDescriptor
            rel_mapping: RelationshipMapping

            if native_rel_descr.name is None:
                continue
            name = native_rel_descr.name
            dest_mapper = Deferred(lambda: self.query_mapper_by_native(native_rel_descr.destination))  # type: ignore
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

        return resource_rels, relationship_mappings

    def build_relationship_mapping_from_proto(
        self,
        native_descr: NativeDescriptor,
        relationship_mappings_proto: RelationshipMappingType,
    ) -> typing.Tuple[
        typing.Sequence[ResourceRelationshipDescriptor],
        typing.Sequence[RelationshipMapping],
    ]:
        resource_rels: typing.List[ResourceRelationshipDescriptor] = []
        relationship_mappings: typing.List[RelationshipMapping] = []

        native_rel_attr_descrs = {
            rel_descr.name: rel_descr for rel_descr in native_descr.relationships
        }

        for serde_side, native_side in relationship_mappings_proto:
            resource_rel_descr: ResourceRelationshipDescriptor
            rel_mapping: RelationshipMapping

            native_rel_descr = native_rel_attr_descrs[native_side]
            dest_mapper = Deferred(lambda: self.query_mapper_by_native(native_rel_descr.destination))  # type: ignore
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

        return resource_rels, relationship_mappings

    def __call__(
        self, meta: Meta, native_descr: NativeDescriptor
    ) -> typing.Tuple[
        ResourceDescriptor, typing.Sequence[AttributeMapping], typing.Sequence[RelationshipMapping]
    ]:
        resource_attrs: typing.Sequence[ResourceAttributeDescriptor]
        resource_rels: typing.Sequence[ResourceRelationshipDescriptor]
        attribute_mappings: typing.Sequence[AttributeMapping]
        relationship_mappings: typing.Sequence[RelationshipMapping]

        attribute_mappings_proto = meta.attribute_mappings
        predefined_resource_attrs: typing.Optional[
            typing.Mapping[str, ResourceAttributeDescriptor]
        ] = None

        if meta.serde_side.attributes:
            predefined_resource_attrs = {}
            for attr_descr in meta.serde_side.attributes:
                predefined_resource_attrs[assert_not_none(attr_descr.name)] = attr_descr
        resource_attr_overrides = meta.serde_side.attribute_overrides

        if attribute_mappings_proto is None:
            resource_attrs, attribute_mappings = self.build_attribute_mapping_auto(
                native_descr,
                predefined_resource_attrs,
                resource_attr_overrides,
            )
        else:
            resource_attrs, attribute_mappings = self.build_attribute_mapping_from_proto(
                native_descr,
                predefined_resource_attrs,
                resource_attr_overrides,
                attribute_mappings_proto,
            )

        relationship_mappings_proto = meta.relationship_mappings
        if relationship_mappings_proto is None:
            resource_rels, relationship_mappings = self.build_relationship_mapping_auto(
                native_descr
            )
        else:
            resource_rels, relationship_mappings = self.build_relationship_mapping_from_proto(
                native_descr, relationship_mappings_proto
            )

        return (
            ResourceDescriptor(
                name=self.info_extractor.extract_descriptor_name_for_serde(native_descr),
                attributes=resource_attrs,
                relationships=resource_rels,
            ),
            attribute_mappings,
            relationship_mappings,
        )

    def __init__(
        self,
        info_extractor: InfoExtractor,
        query_mapper_by_native: typing.Callable[[NativeDescriptor], Mapper],
        converter_factory: ConverterFactory,
    ):
        self.info_extractor = info_extractor
        self.query_mapper_by_native = query_mapper_by_native  # type: ignore
        self.converter_factory = converter_factory


def build_mapping(
    meta: Meta,
    native_descr: NativeDescriptor,
    info_extractor: InfoExtractor,
    query_mapper_by_native: typing.Callable[[NativeDescriptor], Mapper],
    converter_factory: ConverterFactory,
) -> typing.Tuple[
    ResourceDescriptor, typing.Sequence[AttributeMapping], typing.Sequence[RelationshipMapping]
]:
    return MapperBuilder(
        info_extractor=info_extractor,
        query_mapper_by_native=query_mapper_by_native,
        converter_factory=converter_factory,
    )(meta, native_descr)
