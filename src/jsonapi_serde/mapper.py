import abc
import collections.abc
import dataclasses
import enum
import typing

from .exceptions import (
    AttributeNotFoundError,
    ImmutableAttributeError,
    InvalidStructureError,
    RelationshipNotFoundError,
)
from .interfaces import (  # noqa: F401
    Endpoint,
    MutationContext,
    NativeAttributeDescriptor,
    NativeBuilder,
    NativeDescriptor,
    NativeRelationshipDescriptor,
    NativeToManyRelationshipBuilder,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipBuilder,
    NativeToOneRelationshipDescriptor,
    PaginatedEndpoint,
)
from .models import (
    ResourceAttributeDescriptor,
    ResourceDescriptor,
    ResourceRelationshipDescriptor,
    ResourceToManyRelationshipDescriptor,
    ResourceToOneRelationshipDescriptor,
)
from .serde.builders import (
    CollectionDocumentBuilder,
    DocumentBuilder,
    ResourceIdReprBuilder,
    ResourceReprBuilder,
    SingletonDocumentBuilder,
    ToManyRelDocumentBuilder,
    ToManyRelReprBuilder,
    ToOneRelDocumentBuilder,
    ToOneRelReprBuilder,
)
from .serde.models import (
    AttributeValue,
    LinksRepr,
    ResourceIdRepr,
    ResourceRepr,
    Source,
)
from .serde.utils import JSONPointer
from .utils import assert_not_none


class ToSerdeContext(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def select_attribute(self, mapping: "AttributeMapping") -> bool:
        ...  # pragma: nocover

    @abc.abstractmethod
    def select_relationship(self, mapping: "RelationshipMapping") -> bool:
        ...  # pragma: nocover

    @abc.abstractmethod
    def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_to_one_relationship_endpoint(
        self,
        mapper: "Mapper",
        native_descr: NativeToOneRelationshipDescriptor,
        rel_descr: ResourceToOneRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[Endpoint]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_to_many_relationship_endpoint(
        self,
        mapper: "Mapper",
        native_descr: NativeToManyRelationshipDescriptor,
        rel_descr: ResourceToManyRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[PaginatedEndpoint]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def query_mapper_by_native(self, descr: NativeDescriptor) -> "Mapper":
        ...  # pragma: nocover

    @abc.abstractmethod
    def get_serde_identity_by_native(self, mapper: "Mapper", native: typing.Any) -> str:
        ...  # pragma: nocover


class ToNativeContext(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def select_attribute(self, mapping: "AttributeMapping") -> bool:
        ...  # pragma: nocover

    @abc.abstractmethod
    def select_relationship(self, mapping: "RelationshipMapping") -> bool:
        ...  # pragma: nocover

    @abc.abstractmethod
    def query_mapper_by_serde(self, descr: ResourceDescriptor) -> "Mapper":
        ...  # pragma: nocover

    @abc.abstractmethod
    def query_descriptor_by_type_name(self, name: str) -> ResourceDescriptor:
        ...  # pragma: nocover

    @abc.abstractmethod
    def get_native_identity_by_serde(
        self, mapper: "Mapper", serde: typing.Union[ResourceRepr, ResourceIdRepr]
    ) -> typing.Any:
        ...  # pragma: nocover


class Direction(enum.IntEnum):
    NONE = 0
    TO_SERDE_ONLY = 1
    TO_NATIVE_ONLY = 2
    BIDI = 3


class Operation(enum.Enum):
    CREATE = 1
    UPDATE = 2
    UPDATE_REL = 3
    QUERY_BUILDING = 4
    RETRIEVE = 5


GenericRepr = typing.Union[
    None,
    ResourceRepr,
    typing.Sequence[ResourceRepr],
    ResourceIdRepr,
    typing.Sequence[ResourceIdRepr],
]


@dataclasses.dataclass
class SiteContext:
    op: Operation
    mapper: "Mapper"
    to_native_ctx: typing.Optional[ToNativeContext] = None
    to_serde_ctx: typing.Optional[ToSerdeContext] = None
    mctx: typing.Optional[MutationContext] = None
    sbctx: typing.Optional["SerdeBuilderContext"] = None
    serde: GenericRepr = None
    target: typing.Optional[typing.Any] = None
    rm: typing.Optional["RelationshipMapping"] = None


ResourceFilter = typing.Callable[[SiteContext, GenericRepr], GenericRepr]


NativeBuilderFilter = typing.Callable[
    [SiteContext, GenericRepr, NativeBuilder],
    NativeBuilder,
]


SerdeBuilderFilter = typing.Callable[
    [
        SiteContext,
        typing.Union[ResourceReprBuilder, ResourceIdReprBuilder],
    ],
    typing.Union[ResourceReprBuilder, ResourceIdReprBuilder],
]


Ta0 = typing.TypeVar("Ta0")


class AttributeMapping(typing.Generic[Ta0], metaclass=abc.ABCMeta):
    mapper: typing.Optional["Mapper"] = None
    direction: Direction = Direction.NONE

    def bind(self, mapper: "Mapper") -> "AttributeMapping[Ta0]":
        assert self.mapper is None
        self.mapper = mapper
        return self

    @property
    @abc.abstractmethod
    def serde_side_descrs(self) -> typing.Iterable[ResourceAttributeDescriptor]:
        ...  # pragma: nocover

    @property
    @abc.abstractmethod
    def native_side_descrs(self) -> typing.Iterable[NativeAttributeDescriptor]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def to_serde(self, ctx: ToSerdeContext, blob: Ta0, builder: ResourceReprBuilder) -> None:
        ...  # pragma: nocover

    @abc.abstractmethod
    def to_native(
        self,
        ctx: ToNativeContext,
        site_ctx: SiteContext,
        blob: ResourceRepr,
        builder: NativeBuilder,
    ) -> None:
        ...  # pragma: nocover


Ta1 = typing.TypeVar("Ta1")


class ToOneAttributeMapping(AttributeMapping[Ta1], typing.Generic[Ta1]):
    serde_side: ResourceAttributeDescriptor
    native_side: NativeAttributeDescriptor
    to_serde_factory: typing.Callable[[ToSerdeContext, typing.Any], AttributeValue]
    to_native_factory: typing.Callable[[ToNativeContext, Source, AttributeValue], typing.Any]

    @property
    def serde_side_descrs(self) -> typing.Iterable[ResourceAttributeDescriptor]:
        return [self.serde_side]

    @property
    def native_side_descrs(self) -> typing.Iterable[NativeAttributeDescriptor]:
        return [self.native_side]

    def to_serde(self, ctx: ToSerdeContext, blob: Ta0, builder: ResourceReprBuilder) -> None:
        if self.direction is Direction.TO_NATIVE_ONLY:
            return
        builder.add_attribute(
            assert_not_none(self.serde_side.name),
            self.to_serde_factory(ctx, self.native_side.fetch_value(blob)),  # type: ignore
        )

    def to_native(
        self,
        ctx: ToNativeContext,
        site_ctx: SiteContext,
        blob: ResourceRepr,
        builder: NativeBuilder,
    ) -> None:
        builder[self.native_side] = self.to_native_factory(  # type: ignore
            ctx,  # type: ignore
            (
                blob._source_ / self.serde_side.name  # type: ignore
                if isinstance(blob._source_, JSONPointer)
                else blob._source_
            ),
            self.serde_side.extract_value(blob),
        )

    def __init__(
        self,
        serde_side: ResourceAttributeDescriptor,
        native_side: NativeAttributeDescriptor,
        to_serde_factory: typing.Callable[
            [ToSerdeContext, typing.Sequence[typing.Any]], AttributeValue
        ],
        to_native_factory: typing.Callable[
            [ToNativeContext, Source, AttributeValue], typing.Sequence[typing.Any]
        ],
        direction: Direction,
    ):
        self.serde_side = serde_side
        self.native_side = native_side
        self.to_serde_factory = to_serde_factory  # type: ignore
        self.to_native_factory = to_native_factory  # type: ignore
        self.direction = direction


Ta2 = typing.TypeVar("Ta2")


class ToManyAttributeMapping(AttributeMapping[Ta2], typing.Generic[Ta2]):
    serde_side: ResourceAttributeDescriptor
    native_side: typing.Sequence[NativeAttributeDescriptor]
    to_serde_factory: typing.Callable[[ToSerdeContext, typing.Sequence[typing.Any]], AttributeValue]
    to_native_factory: typing.Callable[
        [ToNativeContext, Source, AttributeValue], typing.Sequence[typing.Any]
    ]

    @property
    def serde_side_descrs(self) -> typing.Iterable[ResourceAttributeDescriptor]:
        return [self.serde_side]

    @property
    def native_side_descrs(self) -> typing.Iterable[NativeAttributeDescriptor]:
        return self.native_side

    def to_serde(self, ctx: ToSerdeContext, blob: Ta0, builder: ResourceReprBuilder) -> None:
        if self.direction is Direction.TO_NATIVE_ONLY:
            return
        builder.add_attribute(
            assert_not_none(self.serde_side.name),
            self.to_serde_factory(  # type: ignore
                ctx, [n.fetch_value(blob) for n in self.native_side]  # type: ignore
            ),
        )

    def to_native(
        self,
        ctx: ToNativeContext,
        site_ctx: SiteContext,
        blob: ResourceRepr,
        builder: NativeBuilder,
    ) -> None:
        result = self.to_native_factory(  # type: ignore
            ctx,  # type: ignore
            (
                blob._source_ / self.serde_side.name  # type: ignore
                if isinstance(blob._source_, JSONPointer)
                else blob._source_
            ),
            self.serde_side.extract_value(blob),
        )  # type: ignore
        if len(result) != len(self.native_side):
            raise ValueError(
                f"serde side expected to yield {len(self.native_side)} items, got {len(result)}"
            )
        for n, v in zip(self.native_side, result):
            builder[n] = v

    def __init__(
        self,
        serde_side: ResourceAttributeDescriptor,
        native_side: typing.Sequence[NativeAttributeDescriptor],
        to_serde_factory: typing.Callable[
            [ToSerdeContext, typing.Sequence[typing.Any]], AttributeValue
        ],
        to_native_factory: typing.Callable[
            [ToNativeContext, Source, AttributeValue], typing.Sequence[typing.Any]
        ],
        direction: Direction,
    ):
        self.serde_side = serde_side
        self.native_side = native_side
        self.to_serde_factory = to_serde_factory  # type: ignore
        self.to_native_factory = to_native_factory  # type: ignore
        self.direction = direction


Ta3 = typing.TypeVar("Ta3")


class ManyToOneAttributeMapping(AttributeMapping[Ta3], typing.Generic[Ta3]):
    serde_side: typing.Sequence[ResourceAttributeDescriptor]
    native_side: NativeAttributeDescriptor
    to_serde_factory: typing.Callable[[ToSerdeContext, typing.Any], typing.Sequence[AttributeValue]]
    to_native_factory: typing.Callable[
        [ToNativeContext, typing.Sequence[Source], typing.Sequence[AttributeValue]], typing.Any
    ]

    @property
    def serde_side_descrs(self) -> typing.Iterable[ResourceAttributeDescriptor]:
        return self.serde_side

    @property
    def native_side_descrs(self) -> typing.Iterable[NativeAttributeDescriptor]:
        return [self.native_side]

    def to_serde(self, ctx: ToSerdeContext, blob: Ta0, builder: ResourceReprBuilder) -> None:
        if self.direction is Direction.TO_NATIVE_ONLY:
            return
        result = self.to_serde_factory(ctx, self.native_side.fetch_value(blob))  # type: ignore
        if len(result) != len(self.serde_side):
            raise ValueError(
                f"native side expected to yield {len(self.serde_side)} items, got {len(result)}"
            )
        for s, v in zip(self.serde_side, result):
            builder.add_attribute(assert_not_none(s.name), v)

    def to_native(
        self,
        ctx: ToNativeContext,
        site_ctx: SiteContext,
        blob: ResourceRepr,
        builder: NativeBuilder,
    ) -> None:
        builder[self.native_side] = self.to_native_factory(  # type: ignore
            ctx,  # type: ignore
            (
                [blob._source_ / s.name for s in self.serde_side]  # type: ignore
                if isinstance(blob._source_, JSONPointer)
                else blob._source_
            ),
            [s.extract_value(blob) for s in self.serde_side],
        )

    def __init__(
        self,
        serde_side: typing.Sequence[ResourceAttributeDescriptor],
        native_side: NativeAttributeDescriptor,
        to_serde_factory: typing.Callable[
            [ToSerdeContext, typing.Any], typing.Sequence[AttributeValue]
        ],
        to_native_factory: typing.Callable[
            [ToNativeContext, typing.Sequence[Source], typing.Sequence[AttributeValue]],
            typing.Any,
        ],
        direction: Direction,
    ):
        self.serde_side = serde_side
        self.native_side = native_side
        self.to_serde_factory = to_serde_factory  # type: ignore
        self.to_native_factory = to_native_factory  # type: ignore
        self.direction = direction


class RelationshipMapping:
    mapper: typing.Optional["Mapper"] = None
    serde_side: ResourceRelationshipDescriptor
    native_side: NativeRelationshipDescriptor

    def bind(self, mapper: "Mapper") -> "RelationshipMapping":
        assert self.mapper is None
        self.mapper = mapper
        return self

    def __init__(
        self, serde_side: ResourceRelationshipDescriptor, native_side: NativeRelationshipDescriptor
    ):
        self.serde_side = serde_side
        self.native_side = native_side


class SerdeBuilderContext(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def native_visited(
        self, ctx: ToSerdeContext, mapper: "Mapper", dest_mapper: "Mapper", native: typing.Any
    ):
        ...  # pragma: nocover


Tm = typing.TypeVar("Tm")


NativeFilter = typing.Callable[[SiteContext, GenericRepr, Tm], Tm]


class Mapper(typing.Generic[Tm]):
    resource_descr: ResourceDescriptor
    native_descr: NativeDescriptor
    ctx: typing.Optional["MapperContext"]
    resource_filters: typing.Sequence[ResourceFilter]
    native_builder_filters: typing.Sequence[NativeBuilderFilter]
    native_filters: typing.Sequence[NativeFilter[Tm]]
    serde_builder_filters: typing.Sequence[SerdeBuilderFilter]

    _attribute_mappings: typing.Sequence[AttributeMapping[Tm]]
    _relationship_mappings: typing.Sequence[RelationshipMapping]
    _relationship_mappings_by_serde_name: typing.Mapping[str, RelationshipMapping]

    @property
    def attribute_mappings(self) -> typing.Sequence[AttributeMapping[Tm]]:
        return self._attribute_mappings

    @attribute_mappings.setter
    def attribute_mappings(self, value: typing.Iterable[AttributeMapping[Tm]]) -> None:
        self._attribute_mappings = [m.bind(self) for m in value]

    @property
    def relationship_mappings(self) -> typing.Sequence[RelationshipMapping]:
        return self._relationship_mappings

    @relationship_mappings.setter
    def relationship_mappings(self, value: typing.Iterable[RelationshipMapping]) -> None:
        mappings = [m.bind(self) for m in value]
        self._relationship_mappings = mappings
        self._relationship_mappings_by_serde_name = {
            assert_not_none(m.serde_side.name): m for m in mappings
        }

    def _build_native_to_one(
        self,
        ctx: ToNativeContext,
        builder: NativeToOneRelationshipBuilder,
        serde: typing.Optional[ResourceIdRepr],
        native_side: NativeToOneRelationshipDescriptor,
        serde_side: ResourceToOneRelationshipDescriptor,
    ) -> None:
        dest_mapper = ctx.query_mapper_by_serde(serde_side.destination)
        if serde is None:
            builder.set(None)
            return
        assert not isinstance(serde, collections.abc.Sequence)
        if ctx.query_descriptor_by_type_name(serde.type) != dest_mapper.resource_descr:
            raise InvalidStructureError(
                f"resource type {serde.type} is not acceptable in relationship {serde_side.name}"
            )
        id_ = dest_mapper.get_native_identity_by_serde(ctx, serde)
        builder.set(id_)

    def _build_native_to_many(
        self,
        ctx: ToNativeContext,
        builder: NativeToManyRelationshipBuilder,
        serde: typing.Sequence[ResourceIdRepr],
        native_side: NativeToManyRelationshipDescriptor,
        serde_side: ResourceToManyRelationshipDescriptor,
    ) -> None:
        dest_mapper = ctx.query_mapper_by_serde(serde_side.destination)
        assert isinstance(serde, collections.abc.Sequence)
        for dest_repr in typing.cast(typing.Iterable[ResourceIdRepr], serde):
            if ctx.query_descriptor_by_type_name(dest_repr.type) != dest_mapper.resource_descr:
                raise InvalidStructureError(
                    f"resource type {dest_repr.type} is not acceptable in relationship {serde_side.name}"
                )
            id_ = dest_mapper.get_native_identity_by_serde(ctx, dest_repr)
            builder.next(id_)

    def _get_attribute_mapping_by_serde_name(self, source: Source, name: str) -> AttributeMapping:
        for am in self.attribute_mappings:
            if isinstance(am, ToOneAttributeMapping):
                if am.serde_side.name == name:
                    return am
            elif isinstance(am, ToManyAttributeMapping):
                if am.serde_side.name == name:
                    return am
            elif isinstance(am, ManyToOneAttributeMapping):
                if any(resource_attr_descr.name == name for resource_attr_descr in am.serde_side):
                    return am
        raise AttributeNotFoundError(resource=self.resource_descr, name=name, source=source)

    def get_relationship_mapping_by_serde_name(
        self, source: typing.Optional[Source], name: str
    ) -> RelationshipMapping:
        try:
            return self._relationship_mappings_by_serde_name[name]
        except KeyError:
            raise RelationshipNotFoundError(resource=self.resource_descr, name=name, source=source)

    def create_from_serde(
        self, ctx: ToNativeContext, mctx: MutationContext, serde: ResourceRepr
    ) -> Tm:
        site_ctx = SiteContext(
            Operation.CREATE, mapper=self, to_native_ctx=ctx, mctx=mctx, serde=serde
        )

        for rf in self.resource_filters:
            serde = typing.cast(ResourceRepr, rf(site_ctx, serde))

        builder = self.native_descr.new_builder()
        for am in self.attribute_mappings:
            if am.direction is Direction.TO_SERDE_ONLY:
                continue
            try:
                am.to_native(ctx, site_ctx, serde, builder)
            except AttributeNotFoundError:
                if not any(
                    resource_attr_descr.required_on_creation
                    for resource_attr_descr in am.serde_side_descrs
                ):
                    continue
                else:
                    raise

        for rm in self.relationship_mappings:
            if ctx.select_relationship(rm):
                try:
                    dest_repr = rm.serde_side.extract_related(serde)
                except RelationshipNotFoundError:
                    continue
                if isinstance(rm.native_side, NativeToOneRelationshipDescriptor):
                    self._build_native_to_one(
                        ctx,
                        builder.to_one_relationship(rm.native_side),
                        typing.cast(typing.Optional[ResourceIdRepr], dest_repr.data),
                        typing.cast(NativeToOneRelationshipDescriptor, rm.native_side),
                        typing.cast(ResourceToOneRelationshipDescriptor, rm.serde_side),
                    )
                elif isinstance(rm.native_side, NativeToManyRelationshipDescriptor):
                    self._build_native_to_many(
                        ctx,
                        builder.to_many_relationship(rm.native_side),
                        typing.cast(typing.Sequence[ResourceIdRepr], dest_repr.data),
                        typing.cast(NativeToManyRelationshipDescriptor, rm.native_side),
                        typing.cast(ResourceToManyRelationshipDescriptor, rm.serde_side),
                    )
                else:
                    raise AssertionError("should never get here!")

        for nbf in self.native_builder_filters:
            builder = nbf(site_ctx, serde, builder)

        native = builder(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native

    def update_with_serde(
        self,
        ctx: ToNativeContext,
        mctx: MutationContext,
        target: Tm,
        serde: ResourceRepr,
        skip_missing: bool = False,
    ) -> Tm:
        site_ctx = SiteContext(
            Operation.UPDATE, mapper=self, to_native_ctx=ctx, mctx=mctx, serde=serde, target=target
        )

        for rf in self.resource_filters:
            serde = typing.cast(ResourceRepr, rf(site_ctx, serde))

        builder = self.native_descr.new_updater(target)
        for am in self.attribute_mappings:
            if ctx.select_attribute(am):
                if am.direction is Direction.TO_SERDE_ONLY:
                    continue
                try:
                    am.to_native(ctx, site_ctx, serde, builder)
                except AttributeNotFoundError:
                    if skip_missing:
                        continue
                    else:
                        raise
                for resource_attr_descr in am.serde_side_descrs:
                    if resource_attr_descr.immutable:
                        raise ImmutableAttributeError(
                            self.resource_descr,
                            f"attribute {resource_attr_descr.name} is immutable",
                            serde._source_
                            if not isinstance(serde._source_, JSONPointer)
                            else serde._source_ / "attributes" / resource_attr_descr.name,
                        )
        for rm in self.relationship_mappings:
            if ctx.select_relationship(rm):
                try:
                    dest_repr = rm.serde_side.extract_related(serde)
                except RelationshipNotFoundError:
                    continue
                if isinstance(rm.native_side, NativeToOneRelationshipDescriptor):
                    self._build_native_to_one(
                        ctx,
                        builder.to_one_relationship(rm.native_side),
                        typing.cast(typing.Optional[ResourceIdRepr], dest_repr.data),
                        typing.cast(NativeToOneRelationshipDescriptor, rm.native_side),
                        typing.cast(ResourceToOneRelationshipDescriptor, rm.serde_side),
                    )
                elif isinstance(rm.native_side, NativeToManyRelationshipDescriptor):
                    self._build_native_to_many(
                        ctx,
                        builder.to_many_relationship(rm.native_side),
                        typing.cast(typing.Sequence[ResourceIdRepr], dest_repr.data),
                        typing.cast(NativeToManyRelationshipDescriptor, rm.native_side),
                        typing.cast(ResourceToManyRelationshipDescriptor, rm.serde_side),
                    )
                else:
                    raise AssertionError("should never get here!")

        for nbf in self.native_builder_filters:
            builder = nbf(site_ctx, serde, builder)

        native = builder(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native

    def update_to_one_rel_with_serde(
        self,
        ctx: ToNativeContext,
        mctx: MutationContext,
        target: Tm,
        rm: RelationshipMapping,
        serde: typing.Optional[ResourceIdRepr],
    ) -> Tm:
        assert isinstance(rm.native_side, NativeToOneRelationshipDescriptor)

        site_ctx = SiteContext(
            Operation.UPDATE_REL,
            mapper=self,
            to_native_ctx=ctx,
            mctx=mctx,
            serde=serde,
            target=target,
            rm=rm,
        )

        for rf in self.resource_filters:
            serde = typing.cast(typing.Optional[ResourceIdRepr], rf(site_ctx, serde))

        builder = self.native_descr.new_updater(target)
        self._build_native_to_one(
            ctx,
            builder.to_one_relationship(rm.native_side),
            serde,
            typing.cast(NativeToOneRelationshipDescriptor, rm.native_side),
            typing.cast(ResourceToOneRelationshipDescriptor, rm.serde_side),
        )

        for nbf in self.native_builder_filters:
            builder = nbf(site_ctx, serde, builder)

        native = builder(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native

    def update_to_many_rel_with_serde(
        self,
        ctx: ToNativeContext,
        mctx: MutationContext,
        target: Tm,
        rm: RelationshipMapping,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> Tm:
        assert isinstance(rm.native_side, NativeToManyRelationshipDescriptor)

        site_ctx = SiteContext(
            Operation.UPDATE_REL,
            mapper=self,
            to_native_ctx=ctx,
            mctx=mctx,
            serde=serde,
            target=target,
            rm=rm,
        )

        for rf in self.resource_filters:
            serde = typing.cast(typing.Sequence[ResourceIdRepr], rf(site_ctx, serde))

        builder = self.native_descr.new_updater(target)
        self._build_native_to_many(
            ctx,
            builder.to_many_relationship(rm.native_side),
            serde,
            typing.cast(NativeToManyRelationshipDescriptor, rm.native_side),
            typing.cast(ResourceToManyRelationshipDescriptor, rm.serde_side),
        )

        for nbf in self.native_builder_filters:
            builder = nbf(site_ctx, serde, builder)

        native = builder(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native

    def get_native_identity_by_serde(
        self, ctx: ToNativeContext, serde: typing.Union[ResourceIdRepr, ResourceRepr]
    ) -> typing.Any:
        return ctx.get_native_identity_by_serde(self, serde)

    def get_serde_identity_by_native(self, ctx: ToSerdeContext, target: Tm) -> str:
        return ctx.get_serde_identity_by_native(self, target)

    def _build_serde_to_one(
        self,
        ctx: ToSerdeContext,
        rctx: SerdeBuilderContext,
        builder: typing.Union[ToOneRelReprBuilder, ToOneRelDocumentBuilder],
        native: Tm,
        native_side: NativeToOneRelationshipDescriptor,
        serde_side: ResourceToOneRelationshipDescriptor,
    ) -> None:
        dest_mapper = ctx.query_mapper_by_native(native_side.destination)
        ep = ctx.resolve_to_one_relationship_endpoint(self, native_side, serde_side, native)
        if ep is not None:
            builder.links = LinksRepr(self_=ep.get_self())
        dest = native_side.fetch_related(native)
        if dest is not None:
            rctx.native_visited(ctx, self, dest_mapper, dest)
            dest_mapper.build_serde(ctx, rctx, builder.set(), dest)

    def _build_serde_to_many(
        self,
        ctx: ToSerdeContext,
        rctx: SerdeBuilderContext,
        builder: typing.Union[ToManyRelReprBuilder, ToManyRelDocumentBuilder],
        native: Tm,
        native_side: NativeToManyRelationshipDescriptor,
        serde_side: ResourceToManyRelationshipDescriptor,
    ) -> None:
        dest_mapper = ctx.query_mapper_by_native(native_side.destination)
        ep = ctx.resolve_to_many_relationship_endpoint(self, native_side, serde_side, native)
        if ep is not None:
            builder.links = LinksRepr(
                self_=ep.get_self(),
                prev=ep.get_prev(),
                next=ep.get_next(),
                first=ep.get_first(),
                last=ep.get_last(),
            )
        dest = native_side.fetch_related(native)
        for n in dest:
            rctx.native_visited(ctx, self, dest_mapper, n)
            dest_mapper.build_serde(ctx, rctx, builder.next(), n)

    def build_serde_to_one_relationship(
        self,
        ctx: ToSerdeContext,
        rctx: SerdeBuilderContext,
        builder: typing.Union[ToOneRelReprBuilder, ToOneRelDocumentBuilder],
        native: Tm,
        rm: RelationshipMapping,
    ) -> None:
        assert isinstance(rm.native_side, NativeToOneRelationshipDescriptor)
        self._build_serde_to_one(
            ctx,
            rctx,
            builder,
            native,
            typing.cast(NativeToOneRelationshipDescriptor, rm.native_side),
            typing.cast(ResourceToOneRelationshipDescriptor, rm.serde_side),
        )

    def build_serde_to_many_relationship(
        self,
        ctx: ToSerdeContext,
        rctx: SerdeBuilderContext,
        builder: typing.Union[ToManyRelReprBuilder, ToManyRelDocumentBuilder],
        native: Tm,
        rm: RelationshipMapping,
    ) -> None:
        assert isinstance(rm.native_side, NativeToManyRelationshipDescriptor)
        self._build_serde_to_many(
            ctx,
            rctx,
            builder,
            native,
            typing.cast(NativeToManyRelationshipDescriptor, rm.native_side),
            typing.cast(ResourceToManyRelationshipDescriptor, rm.serde_side),
        )

    def _build_serde_relationship(
        self,
        ctx: ToSerdeContext,
        rctx: SerdeBuilderContext,
        builder: ResourceReprBuilder,
        native: Tm,
        rm: RelationshipMapping,
    ) -> None:
        dest_builder: typing.Union[ToOneRelReprBuilder, ToManyRelReprBuilder]
        if isinstance(rm.native_side, NativeToOneRelationshipDescriptor):
            self.build_serde_to_one_relationship(
                ctx,
                rctx,
                builder.next_to_one_relationship(assert_not_none(rm.serde_side.name)),
                native,
                rm,
            )
        elif isinstance(rm.native_side, NativeToManyRelationshipDescriptor):
            self.build_serde_to_many_relationship(
                ctx,
                rctx,
                builder.next_to_many_relationship(assert_not_none(rm.serde_side.name)),
                native,
                rm,
            )
        else:
            raise AssertionError("should never get here!")

    def build_serde(
        self,
        ctx: ToSerdeContext,
        rctx: SerdeBuilderContext,
        builder: typing.Union[ResourceReprBuilder, ResourceIdReprBuilder],
        native: Tm,
    ) -> None:
        site_ctx = SiteContext(
            Operation.RETRIEVE, mapper=self, to_serde_ctx=ctx, sbctx=rctx, target=native
        )

        builder.type = ctx.query_type_name_by_descriptor(self.resource_descr)
        builder.id = self.get_serde_identity_by_native(ctx, native)
        if isinstance(builder, ResourceReprBuilder):
            builder.links = None
            for am in self.attribute_mappings:
                if ctx.select_attribute(am):
                    am.to_serde(ctx, native, builder)
            for rm in self.relationship_mappings:
                if ctx.select_relationship(rm):
                    self._build_serde_relationship(ctx, rctx, builder, native, rm)

        for sbf in self.serde_builder_filters:
            sbf(site_ctx, builder)

    def bind(self, ctx: "MapperContext") -> None:
        self.ctx = ctx

    def __init__(
        self,
        resource_descr: ResourceDescriptor,
        native_descr: NativeDescriptor,
        attribute_mappings: typing.Sequence[AttributeMapping],
        relationship_mappings: typing.Sequence[RelationshipMapping],
        ctx: typing.Optional["MapperContext"] = None,
        resource_filters: typing.Sequence[ResourceFilter] = (),
        native_builder_filters: typing.Sequence[NativeBuilderFilter] = (),
        native_filters: typing.Sequence[NativeFilter[Tm]] = (),
        serde_builder_filters: typing.Sequence[SerdeBuilderFilter] = (),
    ):
        self.resource_descr = resource_descr
        self.native_descr = native_descr
        self.attribute_mappings = attribute_mappings
        self.relationship_mappings = relationship_mappings
        self.ctx = ctx
        self.resource_filters = resource_filters
        self.native_builder_filters = native_builder_filters
        self.native_filters = native_filters
        self.serde_builder_filters = serde_builder_filters


class Driver(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_serde_identity_by_native(self, mapper: Mapper, native: typing.Any) -> str:
        ...  # pragma: nocover

    @abc.abstractmethod
    def get_native_identity_by_serde(
        self, mapper: Mapper, serde: typing.Union[ResourceRepr, ResourceIdRepr]
    ) -> typing.Any:
        ...  # pragma: nocover


class SerdeTypeResolver(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
        ...  # pragma: nocover

    @abc.abstractmethod
    def query_descriptor_by_type_name(self, name: str) -> ResourceDescriptor:
        ...  # pragma: nocover

    @abc.abstractmethod
    def mapper_added(self, mapper: Mapper) -> None:
        ...  # pragma: nocover


class EndpointResolver(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def resolve_singleton_endpoint(self, mapper: Mapper) -> typing.Optional[Endpoint]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_collection_endpoint(self, mapper: Mapper) -> typing.Optional[PaginatedEndpoint]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_to_one_relationship_endpoint(
        self,
        mapper: Mapper,
        native_descr: NativeToOneRelationshipDescriptor,
        rel_descr: ResourceToOneRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[Endpoint]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_to_many_relationship_endpoint(
        self,
        mapper: Mapper,
        native_descr: NativeToManyRelationshipDescriptor,
        rel_descr: ResourceToManyRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[PaginatedEndpoint]:
        ...  # pragma: nocover


class MapperContext:
    driver: Driver
    serde_type_resolver: SerdeTypeResolver
    endpoint_resolver: EndpointResolver
    _native_descr_to_mapper_mappings: typing.MutableMapping[NativeDescriptor, Mapper]
    _resource_descr_to_mapper_mappings: typing.MutableMapping[ResourceDescriptor, Mapper]
    _native_class_to_descr_mappings: typing.MutableMapping[typing.Type, NativeDescriptor]

    class _ToSerdeContext(ToSerdeContext):
        outer_ctx: "MapperContext"
        _select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]]
        _select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]]

        def select_attribute(self, mapping: AttributeMapping) -> bool:
            return self._select_attribute(mapping) if self._select_attribute is not None else True

        def select_relationship(self, mapping: RelationshipMapping) -> bool:
            return (
                self._select_relationship(mapping)
                if self._select_relationship is not None
                else True
            )

        def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
            return self.outer_ctx.serde_type_resolver.query_type_name_by_descriptor(descr)

        def resolve_to_one_relationship_endpoint(
            self,
            mapper: Mapper,
            native_descr: NativeToOneRelationshipDescriptor,
            rel_descr: ResourceToOneRelationshipDescriptor,
            native: typing.Any,
        ) -> typing.Optional[Endpoint]:
            return self.outer_ctx.endpoint_resolver.resolve_to_one_relationship_endpoint(
                mapper, native_descr, rel_descr, native
            )

        def resolve_to_many_relationship_endpoint(
            self,
            mapper: Mapper,
            native_descr: NativeToManyRelationshipDescriptor,
            rel_descr: ResourceToManyRelationshipDescriptor,
            native: typing.Any,
        ) -> typing.Optional[PaginatedEndpoint]:
            return self.outer_ctx.endpoint_resolver.resolve_to_many_relationship_endpoint(
                mapper, native_descr, rel_descr, native
            )

        def query_mapper_by_native(self, descr: NativeDescriptor) -> Mapper:
            return self.outer_ctx.query_mapper_by_native(descr)

        def get_serde_identity_by_native(self, mapper: Mapper, native: typing.Any) -> str:
            return self.outer_ctx.driver.get_serde_identity_by_native(mapper, native)

        def __init__(
            self,
            outer_ctx: "MapperContext",
            select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]],
            select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]],
        ):
            self.outer_ctx = outer_ctx
            self._select_attribute = select_attribute
            self._select_relationship = select_relationship

    class _ToNativeContext(ToNativeContext):
        outer_ctx: "MapperContext"
        _select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]]
        _select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]]

        def select_attribute(self, mapping: "AttributeMapping") -> bool:
            return self._select_attribute(mapping) if self._select_attribute is not None else True

        def select_relationship(self, mapping: "RelationshipMapping") -> bool:
            return (
                self._select_relationship(mapping)
                if self._select_relationship is not None
                else True
            )

        def query_mapper_by_serde(self, descr: ResourceDescriptor) -> Mapper:
            return self.outer_ctx.query_mapper_by_serde(descr)

        def get_native_identity_by_serde(
            self, mapper: Mapper, serde: typing.Union[ResourceRepr, ResourceIdRepr]
        ) -> typing.Any:
            return self.outer_ctx.driver.get_native_identity_by_serde(mapper, serde)

        def query_descriptor_by_type_name(self, name: str) -> ResourceDescriptor:
            return self.outer_ctx.serde_type_resolver.query_descriptor_by_type_name(name)

        def __init__(
            self,
            outer_ctx: "MapperContext",
            select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]],
            select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]],
        ):
            self.outer_ctx = outer_ctx
            self._select_attribute = select_attribute
            self._select_relationship = select_relationship

    class _SerdeBuilderContext(SerdeBuilderContext):
        doc_builder: DocumentBuilder
        visited: typing.Set

        def native_visited(
            self, ctx: ToSerdeContext, mapper: Mapper, dest_mapper: Mapper, native: typing.Any
        ):
            if native in self.visited:
                return
            self.visited.add(native)
            builder = self.doc_builder.next_included()
            dest_mapper.build_serde(ctx, self, builder, native)

        def __init__(self, doc_builder: DocumentBuilder):
            self.doc_builder = doc_builder
            self.visited = set()

    def query_mapper_by_native(self, descr: NativeDescriptor) -> Mapper:
        return self._native_descr_to_mapper_mappings[descr]

    def query_mapper_by_serde(self, descr: ResourceDescriptor) -> Mapper:
        return self._resource_descr_to_mapper_mappings[descr]

    def query_mapper_by_serde_type(self, type_: str) -> Mapper:
        return self.query_mapper_by_serde(
            self.serde_type_resolver.query_descriptor_by_type_name(type_)
        )

    def query_mapper_by_native_class(self, type_: typing.Type) -> Mapper:
        return self.query_mapper_by_native(self._native_class_to_descr_mappings[type_])

    def create_mapper(
        self,
        resource_descr: ResourceDescriptor,
        native_descr: NativeDescriptor,
        attribute_mappings: typing.Sequence[AttributeMapping],
        relationship_mappings: typing.Sequence[RelationshipMapping],
        resource_filters: typing.Sequence[ResourceFilter] = (),
        native_builder_filters: typing.Sequence[NativeBuilderFilter] = (),
        native_filters: typing.Sequence[NativeFilter[Tm]] = (),
        serde_builder_filters: typing.Sequence[SerdeBuilderFilter] = (),
    ) -> Mapper:
        mapper = Mapper[typing.Any](
            resource_descr=resource_descr,
            native_descr=native_descr,
            attribute_mappings=attribute_mappings,
            relationship_mappings=relationship_mappings,
            ctx=self,
            resource_filters=resource_filters,
            native_builder_filters=native_builder_filters,
            native_filters=native_filters,
            serde_builder_filters=serde_builder_filters,
        )
        self._resource_descr_to_mapper_mappings[resource_descr] = mapper
        self._native_descr_to_mapper_mappings[native_descr] = mapper
        self._native_class_to_descr_mappings[native_descr.class_] = native_descr
        self.serde_type_resolver.mapper_added(mapper)
        return mapper

    def create_to_serde_context(
        self,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
    ):
        return self._ToSerdeContext(self, select_attribute, select_relationship)

    def create_to_native_context(
        self,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
    ):
        return self._ToNativeContext(self, select_attribute, select_relationship)

    def create_from_serde(
        self,
        mctx: MutationContext,
        serde: ResourceRepr,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
    ) -> typing.Any:
        resource_descr = self.serde_type_resolver.query_descriptor_by_type_name(serde.type)
        mapper = self._resource_descr_to_mapper_mappings[resource_descr]
        return mapper.create_from_serde(
            ctx=self.create_to_native_context(select_attribute, select_relationship),
            mctx=mctx,
            serde=serde,
        )

    Tmc = typing.TypeVar("Tmc")

    def update_with_serde(
        self,
        mctx: MutationContext,
        target: Tmc,
        serde: ResourceRepr,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
        skip_missing: bool = False,
    ) -> Tmc:
        resource_descr = self.serde_type_resolver.query_descriptor_by_type_name(serde.type)
        mapper = self._resource_descr_to_mapper_mappings[resource_descr]
        assert isinstance(target, mapper.native_descr.class_)
        return mapper.update_with_serde(
            ctx=self.create_to_native_context(select_attribute, select_relationship),
            mctx=mctx,
            target=target,
            serde=serde,
            skip_missing=skip_missing,
        )

    Tmcr = typing.TypeVar("Tmcr")

    def update_to_one_rel_with_serde(
        self,
        mctx: MutationContext,
        target: Tmcr,
        serde_rel_name: str,
        serde: typing.Optional[ResourceIdRepr],
    ) -> Tmcr:
        mapper = self.query_mapper_by_native_class(type(target))
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        return mapper.update_to_one_rel_with_serde(
            ctx=self.create_to_native_context(None), mctx=mctx, target=target, rm=rm, serde=serde
        )

    Tmcrm = typing.TypeVar("Tmcrm")

    def update_to_many_rel_with_serde(
        self,
        mctx: MutationContext,
        target: Tmcrm,
        serde_rel_name: str,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> Tmcrm:
        mapper = self.query_mapper_by_native_class(type(target))
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        return mapper.update_to_many_rel_with_serde(
            ctx=self.create_to_native_context(None), mctx=mctx, target=target, rm=rm, serde=serde
        )

    def _new_singleton_document_builder(self) -> SingletonDocumentBuilder:
        return SingletonDocumentBuilder()

    def _new_collection_document_builder(self) -> CollectionDocumentBuilder:
        return CollectionDocumentBuilder()

    def _new_to_one_rel_document_builder(self) -> ToOneRelDocumentBuilder:
        return ToOneRelDocumentBuilder()

    def _new_to_many_rel_document_builder(self) -> ToManyRelDocumentBuilder:
        return ToManyRelDocumentBuilder()

    Tss = typing.TypeVar("Tss")

    def build_serde_single(
        self,
        native: Tss,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
    ) -> SingletonDocumentBuilder:
        builder = self._new_singleton_document_builder()
        mapper = self.query_mapper_by_native_class(type(native))
        ep = self.endpoint_resolver.resolve_singleton_endpoint(mapper)
        if ep is not None:
            builder.links = LinksRepr(self_=ep.get_self())
        rctx = self._SerdeBuilderContext(builder)
        mapper.build_serde(
            ctx=self.create_to_serde_context(
                select_attribute=select_attribute, select_relationship=select_relationship
            ),
            rctx=rctx,
            builder=builder.data,
            native=native,
        )
        return builder

    Tsc = typing.TypeVar("Tsc")

    def build_serde_collection(
        self,
        native_: typing.Type[Tsc],
        natives: typing.Iterable[Tsc],
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
    ) -> CollectionDocumentBuilder:
        builder = self._new_collection_document_builder()
        mapper = self.query_mapper_by_native_class(native_)
        ep = self.endpoint_resolver.resolve_collection_endpoint(mapper)
        if ep is not None:
            builder.links = LinksRepr(
                self_=ep.get_self(),
                prev=ep.get_prev(),
                next=ep.get_next(),
                first=ep.get_first(),
                last=ep.get_last(),
            )
        rctx = self._SerdeBuilderContext(builder)
        for native in natives:
            inner_builder = builder.next()
            mapper.build_serde(
                ctx=self.create_to_serde_context(
                    select_attribute=select_attribute, select_relationship=select_relationship
                ),
                rctx=rctx,
                builder=inner_builder,
                native=native,
            )
        return builder

    Trss = typing.TypeVar("Trss")

    def build_serde_rel_single(
        self,
        native: Trss,
        serde_rel_name: str,
    ) -> ToOneRelDocumentBuilder:
        builder = self._new_to_one_rel_document_builder()
        mapper = self.query_mapper_by_native_class(type(native))
        rctx = self._SerdeBuilderContext(builder)
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        mapper.build_serde_to_one_relationship(
            ctx=self.create_to_serde_context(),
            rctx=rctx,
            builder=builder,
            native=native,
            rm=rm,
        )
        return builder

    Trsc = typing.TypeVar("Trsc")

    def build_serde_rel_collection(
        self,
        native: Trsc,
        serde_rel_name: str,
    ) -> ToManyRelDocumentBuilder:
        builder = self._new_to_many_rel_document_builder()
        mapper = self.query_mapper_by_native_class(type(native))
        rctx = self._SerdeBuilderContext(builder)
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        mapper.build_serde_to_many_relationship(
            ctx=self.create_to_serde_context(),
            rctx=rctx,
            builder=builder,
            native=native,
            rm=rm,
        )
        return builder

    def __init__(
        self,
        driver: Driver,
        serde_type_resolver: SerdeTypeResolver,
        endpoint_resolver: EndpointResolver,
    ):
        self.driver = driver
        self.serde_type_resolver = serde_type_resolver
        self.endpoint_resolver = endpoint_resolver
        self._native_descr_to_mapper_mappings = {}
        self._resource_descr_to_mapper_mappings = {}
        self._native_class_to_descr_mappings = {}
