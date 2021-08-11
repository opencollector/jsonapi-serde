import abc
import collections.abc
import dataclasses
import enum
import typing

from .deferred import Deferred
from .exceptions import (
    AttributeNotFoundError,
    GenericConstraintError,
    ImmutableAttributeError,
    InvalidStructureError,
    NativeRelationshipNotFoundError,
    RelationshipNotFoundError,
)
from .interfaces import (  # noqa: F401
    MutationContext,
    MutatorDescriptor,
    NativeAttributeDescriptor,
    NativeBuilder,
    NativeDescriptor,
    NativeRelationshipDescriptor,
    NativeToManyRelationshipBuilder,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipBuilder,
    NativeToOneRelationshipDescriptor,
    NativeUpdater,
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
    ResourceReprCollectionBuilder,
    SingletonDocumentBuilder,
    ToManyRelDocumentBuilder,
    ToManyRelReprBuilder,
    ToOneRelDocumentBuilder,
    ToOneRelReprBuilder,
)
from .serde.models import (
    URL,
    AttributeValue,
    LinksRepr,
    ResourceIdRepr,
    ResourceRepr,
    Source,
)
from .serde.utils import JSONPointer
from .utils import assert_not_none


@dataclasses.dataclass
class PaginatedEndpoint:
    """
    A ``PaginatedEndpoint`` describes an endpoint that provides collection of resources.
    """

    self_: URL
    """
    Value for ``self`` key of a JSONAPI's links object.
    """

    prev: typing.Optional[URL] = None
    """
    Value for ``prev`` key of a JSONAPI's links object.

    This field is optional when the previous page is not available.
    """

    next: typing.Optional[URL] = None
    """
    Value for ``next`` key of a JSONAPI's links object. This field is optional.
    """

    first: typing.Optional[URL] = None
    """
    Value for ``first`` key of a JSONAPI's links object.  This field is optional.
    """

    last: typing.Optional[URL] = None
    """
    Value for ``last`` key of a JSONAPI's links object.  This field is optional.
    """


class RelationshipPart(enum.IntEnum):
    NONE = 0
    """Indicates nothing should be selected"""
    LINKS = 1
    """Indicates only links to the resources needs to be included"""
    DATA = 2
    """Indicates only data to the resource needs to be included"""
    ALL = -1
    """Indicates everything needs to be included"""


class ToSerdeContext(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def select_attribute(self, mapping: "AttributeMapping") -> bool:
        """
        Determines the given attribute needs to be included in the response

        :param AttributeMapping mapping: an :py:class:`AttributeMapping` object that describes an attribute.
        :return: A boolean value.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def select_relationship(self, mapping: "RelationshipMapping") -> RelationshipPart:
        """
        Determines the given relatioship needs to be included in the response

        :param RelationshipMapping mapping: an :py:class:`RelationshipMapping` object that describes a relationship.
        :return: A RelationshipMapping value.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
        """
        Returns a resource name that corresponds to a resource descriptor.

        :param ResourceDescriptor descr: a :py:class:`ResourceDescriptor`.
        :return: A string representation of the resource name.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_singleton_endpoint(
        self, mapper: "Mapper", native: typing.Any
    ) -> typing.Optional[URL]:
        """
        Resolves a URL for a single resource that is described by a mapper and a native object.
        Returns :py:const:`None` If no URL is designated.
        :param Mapper mapper: a mapper object that corresponds to a resource.
        :param Any native: a native object.
        :return: a URL for the resource or :py:const:`None`.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_collection_endpoint(
        self, mapper: "Mapper", natives: typing.Iterable[typing.Any]
    ) -> typing.Optional[PaginatedEndpoint]:
        """
        Resolves URLs for a collection of resources that are described by a mapper and a native object.
        Returns :py:const:`None` If no URL is designated.
        :param Mapper mapper: a mapper object that corresponds to a resource.
        :param Iterable[Any] native: an iterable of native objects.
        :return: a :py:class:`PaginatedEndpoint` object that stores a set of URLs.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_to_one_relationship_endpoint(
        self,
        mapper: "Mapper",
        native_descr: NativeToOneRelationshipDescriptor,
        rel_descr: ResourceToOneRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[URL]:
        """
        Resolves a URL for a single relationship to a resource that is described by a mapper,
        relationship descriptors of both sides, and a native object.
        Returns :py:const:`None` If no URL is designated.
        :param Mapper mapper: a mapper object that corresponds to a resource.
        :param NativeToOneRelationshipDescriptor native_descr: a native side relationship descriptor.
        :param ResourceToOneRelationshipDescriptor rel_descr: a JSON-API side relationship descriptor.
        :param Any native: a native object that holds the relationship (not the related one.)
        :return: a URL for the resource or :py:const:`None`.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_to_many_relationship_endpoint(
        self,
        mapper: "Mapper",
        native_descr: NativeToManyRelationshipDescriptor,
        rel_descr: ResourceToManyRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[PaginatedEndpoint]:
        """
        Resolves a URL for a single relationship to a resource that is described by a mapper,
        relationship descriptors of both sides, and a native object.
        Returns :py:const:`None` If no URL is designated.
        :param Mapper mapper: a mapper object that corresponds to a resource.
        :param NativeToManyRelationshipDescriptor native_descr: a native side relationship descriptor.
        :param ResourceToManyRelationshipDescriptor rel_descr: a JSON-API side relationship descriptor.
        :param Any native: a native object that holds the relationship (not the related ones.)
        :return: a URL for the resource or :py:const:`None`.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def query_mapper_by_native(self, descr: NativeDescriptor) -> "Mapper":
        """
        Resolves a mapper from the specified native-side resource descriptor.
        The returned mapper has its :py:attr:`native_descr` set to the object identical to the argument.
        :param NativeDescriptor descr: a :py:class:`NativeDescriptor` object.
        :return: a :py:class:`Mapper` object that corresponds to the descriptor.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def get_serde_identity_by_native(self, mapper: "Mapper", native: typing.Any) -> str:
        """
        Build a string representation of a JSON-API identity of the given native object for use in
        serde.
        :param Mapper mapper: a mapper object that maps the native object.
        :param Any native: a native object.
        :return: a string that represents a JSON-API identity.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def to_one_relationship_visited(
        self,
        native_side: NativeToOneRelationshipDescriptor,
        serde_side: ResourceToOneRelationshipDescriptor,
        mapper: "Mapper",
        dest_mapper: "Mapper",
        native: typing.Any,
        dest_available: bool,
        dest: typing.Optional[typing.Any],
    ) -> None:
        """
        Called when a one-to-one relationship is visited during serialization.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def to_many_relationship_visited(
        self,
        native_side: NativeToManyRelationshipDescriptor,
        serde_side: ResourceToManyRelationshipDescriptor,
        mapper: "Mapper",
        dest_mapper: "Mapper",
        native: typing.Any,
        dest: typing.Optional[typing.Iterable[typing.Any]],
    ) -> None:
        """
        Called when a one-to-many relationship is visited during serialization.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def native_visited_pre(
        self,
        mapper: "Mapper",
        native: typing.Any,
        as_rel_ref: bool,
    ) -> None:
        """
        Called when a native object is being visited during serialization.

        :param Mapper mapper: The mapper object that takes care of the native object.
        :param Any native: The native object in question.
        :param bool as_rel_ref: Given :py:const:`True` if the native object is being visited for relationship reference.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def native_visited(
        self,
        mapper: "Mapper",
        native: typing.Any,
        as_rel_ref: bool,
    ) -> None:
        """
        Called every time when a native object has been visited during serialization.

        :param Mapper mapper: The mapper object that takes care of the native object.
        :param Any native: The native object in question.
        :param bool as_rel_ref: Given :py:const:`True` if the native object has been visited for relationship reference.
        """
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
    serde: GenericRepr = None
    target: typing.Union[typing.Any, typing.Iterable[typing.Any], None] = None
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


@dataclasses.dataclass
class MutatorDescriptorImpl(MutatorDescriptor):
    descrs: typing.Sequence[ResourceAttributeDescriptor]
    serde: ResourceRepr

    def raise_immutable_attribute_error(self) -> None:
        # TODO: handle multiple resource attributes
        assert self.descrs[0].parent is not None
        raise ImmutableAttributeError(
            self.descrs[0].parent,
            f"attribute {self.descrs[0].name} is immutable",
            self.serde._source_
            if not isinstance(self.serde._source_, JSONPointer)
            else self.serde._source_ / "attributes" / self.descrs[0].name,
        )


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
        if self.serde_side.immutable:
            builder.mark_immutable(
                self.native_side, MutatorDescriptorImpl((self.serde_side,), blob)
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
        mutator_descr = MutatorDescriptorImpl((self.serde_side,), blob)
        for n, v in zip(self.native_side, result):
            builder[n] = v
            if self.serde_side.immutable:
                builder.mark_immutable(n, mutator_descr)

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
        if any(resource_attr_descr.immutable for resource_attr_descr in self.serde_side):
            builder.mark_immutable(self.native_side, MutatorDescriptorImpl(self.serde_side, blob))

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
    _relationship_mappings_by_native_descr: typing.Mapping[
        NativeRelationshipDescriptor, RelationshipMapping
    ]

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
        self._relationship_mappings_by_native_descr = {m.native_side: m for m in mappings}

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
            if not serde_side.allow_null:
                raise GenericConstraintError(
                    f"relationship {serde_side.name} of resource type {self.resource_descr.name} must be specified"
                )
            builder.nullify()
            return
        assert not isinstance(serde, collections.abc.Sequence)
        if ctx.query_descriptor_by_type_name(serde.type) != dest_mapper.resource_descr:
            raise InvalidStructureError(
                f"resource type {serde.type} is not acceptable in relationship {serde_side.name} (expecting {serde_side.destination.name})"
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
            if dest_repr.id is not None:
                assert dest_repr.type is not None
                if ctx.query_descriptor_by_type_name(dest_repr.type) != dest_mapper.resource_descr:
                    raise InvalidStructureError(
                        f"resource type {dest_repr.type} is not acceptable in relationship {serde_side.name}"
                    )
                id_ = dest_mapper.get_native_identity_by_serde(ctx, dest_repr)
                builder.next(id_)
            else:
                raise InvalidStructureError(
                    f"trying to add a null linkage of {dest_repr.type} to relationship {serde_side.name}"
                )

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

    def get_relationship_mapping_by_native_descriptor(
        self, native_rel_descr: NativeRelationshipDescriptor
    ) -> RelationshipMapping:
        try:
            return self._relationship_mappings_by_native_descr[native_rel_descr]
        except KeyError:
            raise NativeRelationshipNotFoundError(
                descr=self.native_descr,
                name=native_rel_descr.name or "?",
            )

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
                    if rm.serde_side.required_on_creation:
                        raise
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

        updater = self.native_descr.new_updater(target)
        for am in self.attribute_mappings:
            if ctx.select_attribute(am):
                if am.direction is Direction.TO_SERDE_ONLY:
                    continue
                try:
                    am.to_native(ctx, site_ctx, serde, updater)
                except AttributeNotFoundError:
                    if skip_missing:
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
                        updater.to_one_relationship(rm.native_side),
                        typing.cast(typing.Optional[ResourceIdRepr], dest_repr.data),
                        typing.cast(NativeToOneRelationshipDescriptor, rm.native_side),
                        typing.cast(ResourceToOneRelationshipDescriptor, rm.serde_side),
                    )
                elif isinstance(rm.native_side, NativeToManyRelationshipDescriptor):
                    self._build_native_to_many(
                        ctx,
                        updater.to_many_relationship(rm.native_side),
                        typing.cast(typing.Sequence[ResourceIdRepr], dest_repr.data),
                        typing.cast(NativeToManyRelationshipDescriptor, rm.native_side),
                        typing.cast(ResourceToManyRelationshipDescriptor, rm.serde_side),
                    )
                else:
                    raise AssertionError("should never get here!")

        for nbf in self.native_builder_filters:
            _updater = nbf(site_ctx, serde, updater)
            assert isinstance(_updater, NativeUpdater)
            updater = _updater

        native = updater(mctx)

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

        updater = self.native_descr.new_updater(target)
        self._build_native_to_one(
            ctx,
            updater.to_one_relationship(rm.native_side),
            serde,
            typing.cast(NativeToOneRelationshipDescriptor, rm.native_side),
            typing.cast(ResourceToOneRelationshipDescriptor, rm.serde_side),
        )

        for nbf in self.native_builder_filters:
            _updater = nbf(site_ctx, serde, updater)
            assert isinstance(_updater, NativeUpdater)
            updater = _updater

        native = updater(mctx)

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

        updater = self.native_descr.new_updater(target)
        self._build_native_to_many(
            ctx,
            updater.to_many_relationship(rm.native_side),
            serde,
            typing.cast(NativeToManyRelationshipDescriptor, rm.native_side),
            typing.cast(ResourceToManyRelationshipDescriptor, rm.serde_side),
        )

        for nbf in self.native_builder_filters:
            _updater = nbf(site_ctx, serde, updater)
            assert isinstance(_updater, NativeUpdater)
            updater = _updater

        native = updater(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native

    def add_to_one_rel_with_serde(
        self,
        ctx: ToNativeContext,
        mctx: MutationContext,
        target: Tm,
        rm: RelationshipMapping,
        serde: typing.Optional[ResourceIdRepr],
    ) -> typing.Tuple[Tm, bool]:
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
            serde = typing.cast(ResourceIdRepr, rf(site_ctx, serde))

        updater = self.native_descr.new_updater(target)
        manip = updater.to_one_relationship_manipulator(
            typing.cast(NativeToOneRelationshipDescriptor, rm.native_side)
        )
        serde_side = typing.cast(ResourceToOneRelationshipDescriptor, rm.serde_side)
        dest_mapper = ctx.query_mapper_by_serde(serde_side.destination)
        p: Deferred[bool]
        if serde is None:
            p = manip.nullify()
        else:
            if ctx.query_descriptor_by_type_name(serde.type) != dest_mapper.resource_descr:
                raise InvalidStructureError(
                    f"resource type {serde.type} is not acceptable in relationship {serde_side.name}"
                )
            id_ = dest_mapper.get_native_identity_by_serde(ctx, serde)
            p = manip.set(id_)

        for nbf in self.native_builder_filters:
            _updater = nbf(site_ctx, serde, updater)
            assert isinstance(_updater, NativeUpdater)
            updater = _updater

        native = updater(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native, p()

    def remove_to_one_rel_with_serde(
        self,
        ctx: ToNativeContext,
        mctx: MutationContext,
        target: Tm,
        rm: RelationshipMapping,
        serde: ResourceIdRepr,
    ) -> typing.Tuple[Tm, bool]:
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
            serde = typing.cast(ResourceIdRepr, rf(site_ctx, serde))

        updater = self.native_descr.new_updater(target)
        manip = updater.to_one_relationship_manipulator(
            typing.cast(NativeToOneRelationshipDescriptor, rm.native_side)
        )
        serde_side = typing.cast(ResourceToOneRelationshipDescriptor, rm.serde_side)
        dest_mapper = ctx.query_mapper_by_serde(serde_side.destination)
        if ctx.query_descriptor_by_type_name(serde.type) != dest_mapper.resource_descr:
            raise InvalidStructureError(
                f"resource type {serde.type} is not acceptable in relationship {serde_side.name}"
            )
        id_ = dest_mapper.get_native_identity_by_serde(ctx, serde)
        p = manip.unset(id_)

        for nbf in self.native_builder_filters:
            _updater = nbf(site_ctx, serde, updater)
            assert isinstance(_updater, NativeUpdater)
            updater = _updater

        native = updater(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native, p()

    def add_to_many_rel_with_serde(
        self,
        ctx: ToNativeContext,
        mctx: MutationContext,
        target: Tm,
        rm: RelationshipMapping,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> typing.Tuple[Tm, typing.Sequence[typing.Tuple[ResourceIdRepr, bool]]]:
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

        updater = self.native_descr.new_updater(target)
        manip = updater.to_many_relationship_manipulator(
            typing.cast(NativeToManyRelationshipDescriptor, rm.native_side)
        )
        serde_side = typing.cast(ResourceToManyRelationshipDescriptor, rm.serde_side)
        dest_mapper = ctx.query_mapper_by_serde(serde_side.destination)
        ps: typing.List[typing.Tuple[ResourceIdRepr, Deferred[bool]]] = []
        for dest_repr in serde:
            if ctx.query_descriptor_by_type_name(dest_repr.type) != dest_mapper.resource_descr:
                raise InvalidStructureError(
                    f"resource type {dest_repr.type} is not acceptable in relationship {serde_side.name}"
                )
            id_ = dest_mapper.get_native_identity_by_serde(ctx, dest_repr)
            ps.append((dest_repr, manip.add(id_)))

        for nbf in self.native_builder_filters:
            _updater = nbf(site_ctx, serde, updater)
            assert isinstance(_updater, NativeUpdater)
            updater = _updater

        native = updater(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native, [(repr_, p()) for repr_, p in ps]

    def remove_to_many_rel_with_serde(
        self,
        ctx: ToNativeContext,
        mctx: MutationContext,
        target: Tm,
        rm: RelationshipMapping,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> typing.Tuple[Tm, typing.Sequence[typing.Tuple[ResourceIdRepr, bool]]]:
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

        updater = self.native_descr.new_updater(target)
        manip = updater.to_many_relationship_manipulator(
            typing.cast(NativeToManyRelationshipDescriptor, rm.native_side)
        )
        serde_side = typing.cast(ResourceToManyRelationshipDescriptor, rm.serde_side)
        dest_mapper = ctx.query_mapper_by_serde(serde_side.destination)
        ps: typing.List[typing.Tuple[ResourceIdRepr, Deferred[bool]]] = []
        for dest_repr in serde:
            if ctx.query_descriptor_by_type_name(dest_repr.type) != dest_mapper.resource_descr:
                raise InvalidStructureError(
                    f"resource type {dest_repr.type} is not acceptable in relationship {serde_side.name}"
                )
            id_ = dest_mapper.get_native_identity_by_serde(ctx, dest_repr)
            ps.append((dest_repr, manip.remove(id_)))

        for nbf in self.native_builder_filters:
            _updater = nbf(site_ctx, serde, updater)
            assert isinstance(_updater, NativeUpdater)
            updater = _updater

        native = updater(mctx)

        for nf in self.native_filters:
            native = nf(site_ctx, serde, native)
        return native, [(repr_, p()) for repr_, p in ps]

    def get_native_identity_by_serde(
        self, ctx: ToNativeContext, serde: typing.Union[ResourceIdRepr, ResourceRepr]
    ) -> typing.Any:
        return ctx.get_native_identity_by_serde(self, serde)

    def get_serde_identity_by_native(self, ctx: ToSerdeContext, target: Tm) -> str:
        return ctx.get_serde_identity_by_native(self, target)

    def _build_serde_to_one(
        self,
        site_ctx: SiteContext,
        builder: typing.Union[ToOneRelReprBuilder, ToOneRelDocumentBuilder],
        native: Tm,
        native_side: NativeToOneRelationshipDescriptor,
        serde_side: ResourceToOneRelationshipDescriptor,
        parts: RelationshipPart,
    ) -> None:
        ctx = site_ctx.to_serde_ctx
        assert ctx is not None
        if parts & RelationshipPart.LINKS:
            ep = ctx.resolve_to_one_relationship_endpoint(self, native_side, serde_side, native)
            if ep is not None:
                builder.links = LinksRepr(self_=ep)
        dest_mapper = ctx.query_mapper_by_native(native_side.destination)
        dest_available: bool = False
        dest: typing.Optional[typing.Any] = None
        if parts & RelationshipPart.DATA:
            dest = native_side.fetch_related(native)
            dest_available = True
            _builder = builder.set()
            if dest is not None:
                ctx.native_visited_pre(self, dest, True)
                dest_mapper._build_serde_rel(site_ctx, _builder, dest)
        ctx.to_one_relationship_visited(
            native_side, serde_side, self, dest_mapper, native, dest_available, dest
        )

    def _build_serde_to_many(
        self,
        site_ctx: SiteContext,
        builder: typing.Union[ToManyRelReprBuilder, ToManyRelDocumentBuilder],
        native: Tm,
        native_side: NativeToManyRelationshipDescriptor,
        serde_side: ResourceToManyRelationshipDescriptor,
        parts: RelationshipPart,
    ) -> None:
        ctx = site_ctx.to_serde_ctx
        assert ctx is not None
        if parts & RelationshipPart.LINKS:
            ep = ctx.resolve_to_many_relationship_endpoint(self, native_side, serde_side, native)
            if ep is not None:
                builder.links = LinksRepr(
                    self_=ep.self_,
                    prev=ep.prev,
                    next=ep.next,
                    first=ep.first,
                    last=ep.last,
                )
        dest_mapper = ctx.query_mapper_by_native(native_side.destination)
        dest = native_side.fetch_related(native)
        for n in dest:
            ctx.native_visited_pre(self, n, True)
        if parts & RelationshipPart.DATA:
            for n in dest:
                dest_mapper._build_serde_rel(site_ctx, builder.next(), n)
            builder.done()
        ctx.to_many_relationship_visited(native_side, serde_side, self, dest_mapper, native, dest)

    def build_serde_to_one_relationship(
        self,
        ctx: ToSerdeContext,
        builder: typing.Union[ToOneRelReprBuilder, ToOneRelDocumentBuilder],
        native: Tm,
        rm: RelationshipMapping,
        parts: RelationshipPart,
    ) -> None:
        assert isinstance(rm.native_side, NativeToOneRelationshipDescriptor)
        site_ctx = SiteContext(Operation.RETRIEVE, mapper=self, to_serde_ctx=ctx, target=native)
        assert isinstance(rm.serde_side, ResourceToOneRelationshipDescriptor)
        self._build_serde_to_one(
            site_ctx,
            builder,
            native,
            rm.native_side,
            rm.serde_side,
            parts,
        )

    def build_serde_to_many_relationship(
        self,
        ctx: ToSerdeContext,
        builder: typing.Union[ToManyRelReprBuilder, ToManyRelDocumentBuilder],
        native: Tm,
        rm: RelationshipMapping,
        parts: RelationshipPart,
    ) -> None:
        assert isinstance(rm.native_side, NativeToManyRelationshipDescriptor)
        site_ctx = SiteContext(Operation.RETRIEVE, mapper=self, to_serde_ctx=ctx, target=native)
        assert isinstance(rm.serde_side, ResourceToManyRelationshipDescriptor)
        self._build_serde_to_many(site_ctx, builder, native, rm.native_side, rm.serde_side, parts)

    def _build_serde_relationship(
        self,
        site_ctx: SiteContext,
        builder: ResourceReprBuilder,
        rm: RelationshipMapping,
        native: Tm,
    ) -> None:
        assert site_ctx.to_serde_ctx is not None
        parts = site_ctx.to_serde_ctx.select_relationship(rm)
        native_side = rm.native_side
        serde_side = rm.serde_side
        if parts:
            if isinstance(native_side, NativeToOneRelationshipDescriptor):
                assert isinstance(serde_side, ResourceToOneRelationshipDescriptor)
                self._build_serde_to_one(
                    site_ctx,
                    builder.next_to_one_relationship(assert_not_none(rm.serde_side.name)),
                    native,
                    native_side,
                    serde_side,
                    parts,
                )
            elif isinstance(native_side, NativeToManyRelationshipDescriptor):
                assert isinstance(serde_side, ResourceToManyRelationshipDescriptor)
                self._build_serde_to_many(
                    site_ctx,
                    builder.next_to_many_relationship(assert_not_none(rm.serde_side.name)),
                    native,
                    native_side,
                    serde_side,
                    parts,
                )
            else:
                raise AssertionError("should never get here!")

    def _build_serde_rel(
        self,
        site_ctx: SiteContext,
        builder: ResourceIdReprBuilder,
        native: Tm,
    ) -> None:
        ctx = site_ctx.to_serde_ctx
        assert ctx is not None
        builder.type = ctx.query_type_name_by_descriptor(self.resource_descr)
        builder.id = self.get_serde_identity_by_native(ctx, native)
        for sbf in self.serde_builder_filters:
            sbf(site_ctx, builder)
        ctx.native_visited(self, native, True)

    def _build_serde(
        self,
        site_ctx: SiteContext,
        builder: ResourceReprBuilder,
        native: Tm,
    ) -> None:
        ctx = site_ctx.to_serde_ctx
        assert ctx is not None
        ctx.native_visited_pre(self, native, False)
        builder.type = ctx.query_type_name_by_descriptor(self.resource_descr)
        builder.id = self.get_serde_identity_by_native(ctx, native)
        ep = ctx.resolve_singleton_endpoint(self, native)
        if ep is not None:
            builder.links = LinksRepr(self_=ep)
        if isinstance(builder, ResourceReprBuilder):
            builder.links = None
            for am in self.attribute_mappings:
                if ctx.select_attribute(am):
                    am.to_serde(ctx, native, builder)
            for rm in self.relationship_mappings:
                self._build_serde_relationship(site_ctx, builder, rm, native)

        for sbf in self.serde_builder_filters:
            sbf(site_ctx, builder)

        ctx.native_visited(self, native, False)

    def build_serde(
        self,
        ctx: ToSerdeContext,
        builder: ResourceReprBuilder,
        native: Tm,
    ) -> None:
        site_ctx = SiteContext(Operation.RETRIEVE, mapper=self, to_serde_ctx=ctx, target=native)
        self._build_serde(site_ctx, builder, native)

    def build_serde_collection(
        self,
        ctx: ToSerdeContext,
        builder: ResourceReprCollectionBuilder,
        natives: typing.Iterable[Tm],
    ) -> None:
        site_ctx = SiteContext(Operation.RETRIEVE, mapper=self, to_serde_ctx=ctx, target=natives)
        ep = ctx.resolve_collection_endpoint(self, natives)
        if ep is not None:
            builder.links = LinksRepr(
                self_=ep.self_,
                prev=ep.prev,
                next=ep.next,
                first=ep.first,
                last=ep.last,
            )
        for native in natives:
            ctx.native_visited_pre(self, native, False)
        for native in natives:
            inner_builder = builder.next()
            self._build_serde(site_ctx, inner_builder, native)
        builder.done()

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
    def resolve_singleton_endpoint(
        self, ctx: ToSerdeContext, mapper: "Mapper", native: typing.Any
    ) -> typing.Optional[URL]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_collection_endpoint(
        self,
        ctx: ToSerdeContext,
        mapper: "Mapper",
        natives: typing.Iterable[typing.Any],
    ) -> typing.Optional[PaginatedEndpoint]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_to_one_relationship_endpoint(
        self,
        ctx: ToSerdeContext,
        mapper: "Mapper",
        native_descr: NativeToOneRelationshipDescriptor,
        rel_descr: ResourceToOneRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[URL]:
        ...  # pragma: nocover

    @abc.abstractmethod
    def resolve_to_many_relationship_endpoint(
        self,
        ctx: ToSerdeContext,
        mapper: "Mapper",
        native_descr: NativeToManyRelationshipDescriptor,
        rel_descr: ResourceToManyRelationshipDescriptor,
        native: typing.Any,
    ) -> typing.Optional[PaginatedEndpoint]:
        ...  # pragma: nocover


IncludeFilter = typing.Callable[
    [
        "MapperContext",
        ToSerdeContext,
        NativeRelationshipDescriptor,
        ResourceRelationshipDescriptor,
        Mapper,
        Mapper,
        typing.Any,
    ],
    bool,
]


class MapperContext:
    driver: Driver
    serde_type_resolver: SerdeTypeResolver
    endpoint_resolver: EndpointResolver
    _native_descr_to_mapper_mappings: typing.MutableMapping[NativeDescriptor, Mapper]
    _resource_descr_to_mapper_mappings: typing.MutableMapping[ResourceDescriptor, Mapper]
    _native_class_to_descr_mappings: typing.MutableMapping[typing.Type, NativeDescriptor]

    class _ToSerdeContext(ToSerdeContext):
        outer_ctx: "MapperContext"
        doc_builder: DocumentBuilder
        _select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]]
        _select_relationship: typing.Optional[
            typing.Callable[[RelationshipMapping], RelationshipPart]
        ]
        traverse_relationship: typing.Optional[
            typing.Callable[
                [
                    "MapperContext",
                    NativeRelationshipDescriptor,
                    ResourceRelationshipDescriptor,
                    Mapper,
                    Mapper,
                    typing.Any,
                    typing.Any,
                ],
                bool,
            ]
        ]
        _include_filter: typing.Optional[IncludeFilter] = None
        _included: typing.Set[typing.Any]
        _traversed: typing.Set[typing.Any]

        def select_attribute(self, mapping: AttributeMapping) -> bool:
            if self._select_attribute is None:
                return True
            return self._select_attribute(mapping)

        def select_relationship(self, mapping: RelationshipMapping) -> RelationshipPart:
            if self._select_relationship is None:
                return RelationshipPart.LINKS
            return self._select_relationship(mapping)

        def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
            return self.outer_ctx.serde_type_resolver.query_type_name_by_descriptor(descr)

        def resolve_singleton_endpoint(
            self, mapper: Mapper, native: typing.Any
        ) -> typing.Optional[URL]:
            return self.outer_ctx.endpoint_resolver.resolve_singleton_endpoint(self, mapper, native)

        def resolve_collection_endpoint(
            self, mapper: Mapper, natives: typing.Iterable[typing.Any]
        ) -> typing.Optional[PaginatedEndpoint]:
            return self.outer_ctx.endpoint_resolver.resolve_collection_endpoint(
                self, mapper, natives
            )

        def resolve_to_one_relationship_endpoint(
            self,
            mapper: Mapper,
            native_descr: NativeToOneRelationshipDescriptor,
            rel_descr: ResourceToOneRelationshipDescriptor,
            native: typing.Any,
        ) -> typing.Optional[URL]:
            return self.outer_ctx.endpoint_resolver.resolve_to_one_relationship_endpoint(
                self, mapper, native_descr, rel_descr, native
            )

        def resolve_to_many_relationship_endpoint(
            self,
            mapper: Mapper,
            native_descr: NativeToManyRelationshipDescriptor,
            rel_descr: ResourceToManyRelationshipDescriptor,
            native: typing.Any,
        ) -> typing.Optional[PaginatedEndpoint]:
            return self.outer_ctx.endpoint_resolver.resolve_to_many_relationship_endpoint(
                self, mapper, native_descr, rel_descr, native
            )

        def query_mapper_by_native(self, descr: NativeDescriptor) -> Mapper:
            return self.outer_ctx.query_mapper_by_native(descr)

        def get_serde_identity_by_native(self, mapper: Mapper, native: typing.Any) -> str:
            return self.outer_ctx.driver.get_serde_identity_by_native(mapper, native)

        def should_include(
            self,
            native_side: NativeRelationshipDescriptor,
            serde_side: ResourceRelationshipDescriptor,
            mapper: Mapper,
            dest_mapper: Mapper,
            native: typing.Any,
        ) -> bool:
            return self._include_filter is not None and self._include_filter(
                self.outer_ctx, self, native_side, serde_side, mapper, dest_mapper, native
            )

        def _traverse_relationships(
            self,
            mapper: Mapper,
            native: typing.Any,
        ):
            for rm in mapper.relationship_mappings:
                native_side = rm.native_side
                serde_side = rm.serde_side
                dest_mapper = self.query_mapper_by_native(native_side.destination)
                if isinstance(native_side, NativeToOneRelationshipDescriptor):
                    assert isinstance(serde_side, ResourceToOneRelationshipDescriptor)
                    self.to_one_relationship_visited(
                        native_side,
                        serde_side,
                        mapper,
                        dest_mapper,
                        native,
                        False,
                        None,
                    )
                elif isinstance(native_side, NativeToManyRelationshipDescriptor):
                    assert isinstance(serde_side, ResourceToManyRelationshipDescriptor)
                    self.to_many_relationship_visited(
                        native_side,
                        serde_side,
                        mapper,
                        dest_mapper,
                        native,
                        None,
                    )
                else:
                    raise AssertionError("never get here")

        def to_one_relationship_visited(
            self,
            native_side: NativeToOneRelationshipDescriptor,
            serde_side: ResourceToOneRelationshipDescriptor,
            mapper: Mapper,
            dest_mapper: Mapper,
            native: typing.Any,
            dest_available: bool,
            dest: typing.Optional[typing.Any],
        ) -> None:
            if native is None:
                return
            if not dest_available:
                dest = native_side.fetch_related(native)
            if dest is None:
                return
            if dest not in self._included and self.should_include(
                native_side, serde_side, mapper, dest_mapper, dest
            ):
                self._included.add(dest)
                _builder = self.doc_builder.next_included()
                dest_mapper.build_serde(self, _builder, dest)
            if (
                dest is not None
                and self.mark_traversed(dest)
                and (
                    self.traverse_relationship is None
                    or self.traverse_relationship(
                        self.outer_ctx, native_side, serde_side, mapper, dest_mapper, native, dest
                    )
                )
            ):
                self._traverse_relationships(dest_mapper, dest)

        def to_many_relationship_visited(
            self,
            native_side: NativeToManyRelationshipDescriptor,
            serde_side: ResourceToManyRelationshipDescriptor,
            mapper: Mapper,
            dest_mapper: Mapper,
            native: typing.Any,
            dest: typing.Optional[typing.Iterable[typing.Any]],
        ) -> None:
            if dest is None:
                dest = native_side.fetch_related(native)
            if dest is None:
                return
            for _native in dest:
                if _native is None:
                    continue
                if (
                    _native is not None
                    and _native not in self._included
                    and self.should_include(native_side, serde_side, mapper, dest_mapper, _native)
                ):
                    self._included.add(_native)
                    _builder = self.doc_builder.next_included()
                    dest_mapper.build_serde(self, _builder, _native)
                if (
                    _native is not None
                    and self.mark_traversed(_native)
                    and (
                        self.traverse_relationship is None
                        or self.traverse_relationship(
                            self.outer_ctx,
                            native_side,
                            serde_side,
                            mapper,
                            dest_mapper,
                            native,
                            _native,
                        )
                    )
                ):
                    self._traverse_relationships(dest_mapper, _native)

        def native_visited_pre(self, mapper: Mapper, native: typing.Any, as_rel_ref: bool) -> None:
            if not as_rel_ref:
                self._included.add(native)

        def native_visited(self, mapper: Mapper, native: typing.Any, as_rel_ref: bool) -> None:
            return

        def mark_traversed(self, native: typing.Any) -> bool:
            if native in self._traversed:
                return False
            self._traversed.add(native)
            return True

        def __init__(
            self,
            outer_ctx: "MapperContext",
            doc_builder: DocumentBuilder,
            select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]],
            select_relationship: typing.Optional[
                typing.Callable[[RelationshipMapping], RelationshipPart]
            ],
            traverse_relationship: typing.Optional[
                typing.Callable[
                    [
                        "MapperContext",
                        NativeRelationshipDescriptor,
                        ResourceRelationshipDescriptor,
                        Mapper,
                        Mapper,
                        typing.Any,
                        typing.Any,
                    ],
                    bool,
                ]
            ],
            include_filter: typing.Optional[IncludeFilter],
        ):
            self.outer_ctx = outer_ctx
            self.doc_builder = doc_builder
            self._select_attribute = select_attribute
            self._select_relationship = select_relationship
            self.traverse_relationship = traverse_relationship
            self._include_filter = include_filter
            self._included = set()
            self._traversed = set()

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
        builder: DocumentBuilder,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[
            typing.Callable[[RelationshipMapping], RelationshipPart]
        ] = None,
        traverse_relationship: typing.Optional[
            typing.Callable[
                [
                    "MapperContext",
                    NativeRelationshipDescriptor,
                    ResourceRelationshipDescriptor,
                    Mapper,
                    Mapper,
                    typing.Any,
                    typing.Any,
                ],
                bool,
            ]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
    ):
        return self._ToSerdeContext(
            outer_ctx=self,
            doc_builder=builder,
            select_attribute=select_attribute,
            select_relationship=select_relationship,
            traverse_relationship=traverse_relationship,
            include_filter=include_filter,
        )

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

    Tmar = typing.TypeVar("Tmar")

    def add_to_one_rel_with_serde(
        self,
        mctx: MutationContext,
        target: Tmar,
        serde_rel_name: str,
        serde: typing.Optional[ResourceIdRepr],
    ) -> typing.Tuple[Tmar, bool]:
        mapper = self.query_mapper_by_native_class(type(target))
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        return mapper.add_to_one_rel_with_serde(
            ctx=self.create_to_native_context(None), mctx=mctx, target=target, rm=rm, serde=serde
        )

    Tmrr = typing.TypeVar("Tmrr")

    def remove_to_one_rel_with_serde(
        self,
        mctx: MutationContext,
        target: Tmrr,
        serde_rel_name: str,
        serde: ResourceIdRepr,
    ) -> typing.Tuple[Tmrr, bool]:
        mapper = self.query_mapper_by_native_class(type(target))
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        return mapper.remove_to_one_rel_with_serde(
            ctx=self.create_to_native_context(None), mctx=mctx, target=target, rm=rm, serde=serde
        )

    Tmarm = typing.TypeVar("Tmarm")

    def add_to_many_rel_with_serde(
        self,
        mctx: MutationContext,
        target: Tmarm,
        serde_rel_name: str,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> typing.Tuple[Tmarm, typing.Sequence[typing.Tuple[ResourceIdRepr, bool]]]:
        mapper = self.query_mapper_by_native_class(type(target))
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        return mapper.add_to_many_rel_with_serde(
            ctx=self.create_to_native_context(None), mctx=mctx, target=target, rm=rm, serde=serde
        )

    Tmrrm = typing.TypeVar("Tmrrm")

    def remove_to_many_rel_with_serde(
        self,
        mctx: MutationContext,
        target: Tmrrm,
        serde_rel_name: str,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> typing.Tuple[Tmarm, typing.Sequence[typing.Tuple[ResourceIdRepr, bool]]]:
        mapper = self.query_mapper_by_native_class(type(target))
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        return mapper.remove_to_many_rel_with_serde(
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
        select_relationship: typing.Optional[
            typing.Callable[[RelationshipMapping], RelationshipPart]
        ] = None,
        traverse_relationship: typing.Optional[
            typing.Callable[
                [
                    "MapperContext",
                    NativeRelationshipDescriptor,
                    ResourceRelationshipDescriptor,
                    Mapper,
                    Mapper,
                    typing.Any,
                    typing.Any,
                ],
                bool,
            ]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
    ) -> SingletonDocumentBuilder:
        builder = self._new_singleton_document_builder()
        ctx = self.create_to_serde_context(
            builder,
            select_attribute=select_attribute,
            select_relationship=select_relationship,
            traverse_relationship=traverse_relationship,
            include_filter=include_filter,
        )
        mapper = self.query_mapper_by_native_class(type(native))
        mapper.build_serde(
            ctx=ctx,
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
        select_relationship: typing.Optional[
            typing.Callable[[RelationshipMapping], RelationshipPart]
        ] = None,
        traverse_relationship: typing.Optional[
            typing.Callable[
                [
                    "MapperContext",
                    NativeRelationshipDescriptor,
                    ResourceRelationshipDescriptor,
                    Mapper,
                    Mapper,
                    typing.Any,
                    typing.Any,
                ],
                bool,
            ]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
    ) -> CollectionDocumentBuilder:
        builder = self._new_collection_document_builder()
        mapper = self.query_mapper_by_native_class(native_)
        ctx = self.create_to_serde_context(
            builder,
            select_attribute=select_attribute,
            select_relationship=select_relationship,
            traverse_relationship=traverse_relationship,
            include_filter=include_filter,
        )
        mapper.build_serde_collection(
            ctx=ctx,
            builder=builder,
            natives=natives,
        )
        return builder

    Trss = typing.TypeVar("Trss")

    def build_serde_rel_single(
        self,
        native: Trss,
        serde_rel_name: str,
        traverse_relationship: typing.Optional[
            typing.Callable[
                [
                    "MapperContext",
                    NativeRelationshipDescriptor,
                    ResourceRelationshipDescriptor,
                    Mapper,
                    Mapper,
                    typing.Any,
                    typing.Any,
                ],
                bool,
            ]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
        parts: RelationshipPart = RelationshipPart.ALL,
    ) -> ToOneRelDocumentBuilder:
        builder = self._new_to_one_rel_document_builder()
        mapper = self.query_mapper_by_native_class(type(native))
        ctx = self.create_to_serde_context(
            builder,
            traverse_relationship=traverse_relationship,
            include_filter=include_filter,
        )
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        mapper.build_serde_to_one_relationship(
            ctx=ctx,
            builder=builder,
            native=native,
            rm=rm,
            parts=parts,
        )
        assert builder.data is not None
        return builder

    Trsc = typing.TypeVar("Trsc")

    def build_serde_rel_collection(
        self,
        native: Trsc,
        serde_rel_name: str,
        traverse_relationship: typing.Optional[
            typing.Callable[
                [
                    "MapperContext",
                    NativeRelationshipDescriptor,
                    ResourceRelationshipDescriptor,
                    Mapper,
                    Mapper,
                    typing.Any,
                    typing.Any,
                ],
                bool,
            ]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
        parts: RelationshipPart = RelationshipPart.ALL,
    ) -> ToManyRelDocumentBuilder:
        builder = self._new_to_many_rel_document_builder()
        mapper = self.query_mapper_by_native_class(type(native))
        rm = mapper.get_relationship_mapping_by_serde_name(None, serde_rel_name)
        ctx = self.create_to_serde_context(
            builder,
            traverse_relationship=traverse_relationship,
            include_filter=include_filter,
        )
        mapper.build_serde_to_many_relationship(
            ctx=ctx,
            builder=builder,
            native=native,
            rm=rm,
            parts=parts,
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
