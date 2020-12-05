import dataclasses
import typing

from ..declarative import AttributeFlags, InfoExtractor
from ..interfaces import (
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
from ..utils import assert_not_none


class PlainMutationContext(MutationContext):
    def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
        ...  # pragma: nocover


class PlainNativeAttributeDescriptor(NativeAttributeDescriptor):
    _name: str
    _type: typing.Type
    _allow_null: bool

    @property
    def name(self) -> typing.Optional[str]:
        return self._name

    @property
    def type(self) -> typing.Optional[typing.Type]:
        return self._type

    @property
    def allow_null(self) -> bool:
        return self._allow_null

    def fetch_value(self, target: typing.Any) -> typing.Any:
        return getattr(target, self._name)

    def store_value(self, target: typing.Any, value: typing.Any) -> typing.Any:
        setattr(target, self._name, value)
        return target

    def __init__(self, name: str, type, allow_null):
        self._name = name
        self._type = type
        self._allow_null = allow_null


class PlainNativeToOneRelationshipDescriptor(NativeToOneRelationshipDescriptor):
    _destination: NativeDescriptor
    _name: str

    @property
    def destination(self) -> NativeDescriptor:
        return self._destination

    @property
    def name(self) -> str:
        return self._name

    def fetch_related(self, target: typing.Any) -> typing.Any:
        return getattr(target, self._name)

    def replace_related(self, target: typing.Any, replace_by: typing.Any) -> None:
        setattr(target, self._name, replace_by)
        return target

    def __init__(self, destination: NativeDescriptor, name: str):
        self._destination = destination
        self._name = name


class PlainToOneRelationshipBuilder(NativeToOneRelationshipBuilder):
    descr: PlainNativeToOneRelationshipDescriptor
    _builder: typing.Optional["PlainBuilder"] = None
    _nullified: bool = False
    _id: typing.Optional[typing.Any] = None

    def nullify(self):
        self._nullified = True

    def set(self, id: typing.Any):
        self._id = id

    def __call__(self, ctx: MutationContext) -> typing.Any:
        if self._nullified:
            assert self._id is None
            return None
        return self._id

    def __init__(self, descr: PlainNativeToOneRelationshipDescriptor):
        self.descr = descr


class PlainNativeToManyRelationshipDescriptor(NativeToManyRelationshipDescriptor):
    _destination: NativeDescriptor
    _name: str

    @property
    def destination(self) -> NativeDescriptor:
        return self._destination

    @property
    def name(self) -> str:
        return self._name

    def fetch_related(self, target: typing.Any) -> typing.Iterable[typing.Any]:
        return getattr(target, self._name)

    def replace_related(self, target: typing.Any, replace_by: typing.Iterable[typing.Any]) -> None:
        getattr(target, self._name)[:] = replace_by
        return target

    def __init__(self, destination: NativeDescriptor, name: str):
        self._destination = destination
        self._name = name


class PlainToManyRelationshipBuilder(NativeToManyRelationshipBuilder):
    descr: PlainNativeToManyRelationshipDescriptor
    _ids: typing.List[typing.Any]

    def next(self, id: typing.Any):
        self._ids.append(id)

    def __call__(self, ctx: MutationContext) -> typing.Sequence[typing.Any]:
        return self._ids

    def __init__(self, descr: PlainNativeToManyRelationshipDescriptor):
        self.descr = descr
        self._ids = []


class PlainBuilderBase(NativeBuilder):
    descr: "PlainNativeDescriptor"
    attrs: typing.Dict[PlainNativeAttributeDescriptor, typing.Any]
    relationships: typing.Dict[
        typing.Union[
            PlainNativeToOneRelationshipDescriptor, PlainNativeToManyRelationshipDescriptor
        ],
        typing.Union[NativeToOneRelationshipBuilder, NativeToManyRelationshipBuilder],
    ]

    def __setitem__(self, descr: NativeAttributeDescriptor, v: typing.Any) -> None:
        assert isinstance(descr, PlainNativeAttributeDescriptor)
        self.attrs[descr] = v

    def to_one_relationship(
        self, rel_descr: NativeToOneRelationshipDescriptor
    ) -> NativeToOneRelationshipBuilder:
        assert isinstance(rel_descr, PlainNativeToOneRelationshipDescriptor)
        builder = PlainToOneRelationshipBuilder(rel_descr)
        self.relationships[rel_descr] = builder
        return builder

    def to_many_relationship(
        self,
        rel_descr: NativeToManyRelationshipDescriptor,
    ) -> NativeToManyRelationshipBuilder:
        assert isinstance(rel_descr, PlainNativeToManyRelationshipDescriptor)
        builder = PlainToManyRelationshipBuilder(rel_descr)
        self.relationships[rel_descr] = builder
        return builder

    def __init__(self, descr: "PlainNativeDescriptor"):
        self.descr = descr
        self.attrs = {}
        self.relationships = {}


class PlainBuilder(PlainBuilderBase):
    def __call__(self, ctx: MutationContext) -> typing.Any:
        assert isinstance(ctx, PlainMutationContext)
        attrs = {descr.name: v for descr, v in self.attrs.items() if descr.name is not None}
        rels = {}
        for descr, rb in self.relationships.items():
            if descr.name is None:
                continue
            if isinstance(rb, PlainToOneRelationshipBuilder):
                rels[descr.name] = ctx.query_by_identity(descr.destination, id=rb(ctx))
            elif isinstance(rb, PlainToManyRelationshipBuilder):
                rels[descr.name] = [
                    ctx.query_by_identity(descr.destination, id_) for id_ in rb(ctx)
                ]
        return self.descr.class_(**attrs, **rels)

    def __init__(self, descr: "PlainNativeDescriptor"):
        super().__init__(descr)


class PlainUpdater(PlainBuilderBase):
    obj: typing.Any

    def __call__(self, ctx: MutationContext) -> typing.Any:
        assert isinstance(ctx, PlainMutationContext)
        for descr, v in self.attrs.items():
            descr.store_value(self.obj, v)
        for rel_descr, rb in self.relationships.items():
            if isinstance(rb, PlainToOneRelationshipBuilder):
                rel_descr.replace_related(
                    self.obj, ctx.query_by_identity(rel_descr.destination, id=rb(ctx))
                )
            elif isinstance(rb, PlainToManyRelationshipBuilder):
                rel_descr.replace_related(
                    self.obj, (ctx.query_by_identity(rel_descr.destination, id_) for id_ in rb(ctx))
                )
        return self.obj

    def __init__(self, descr: "PlainNativeDescriptor", obj: typing.Any):
        super().__init__(descr)
        assert isinstance(obj, descr.class_)
        self.obj = obj


class PlainNativeDescriptor(NativeDescriptor):
    _class_: type
    _attributes: typing.Sequence[NativeAttributeDescriptor]
    _relationships: typing.Sequence[NativeRelationshipDescriptor]

    @property
    def class_(self) -> type:
        return self._class_

    def new_builder(self) -> NativeBuilder:
        return PlainBuilder(self)

    def new_updater(self, target: typing.Any) -> NativeBuilder:
        return PlainUpdater(self, target)

    @property
    def attributes(self) -> typing.Sequence[NativeAttributeDescriptor]:
        return self._attributes

    @property
    def relationships(self) -> typing.Sequence[NativeRelationshipDescriptor]:
        return self._relationships

    def get_identity(self, target: typing.Any) -> str:
        return target.id

    def __init__(
        self,
        class_: type,
        attributes: typing.Sequence[NativeAttributeDescriptor] = (),
        relationships: typing.Sequence[NativeRelationshipDescriptor] = (),
    ):
        self._class_ = class_
        self._attributes = attributes
        self._relationships = relationships


@dataclasses.dataclass
class DummyEndpoint(Endpoint):
    self_: str

    def get_self(self) -> str:
        return self.self_


@dataclasses.dataclass
class DummyPaginatedEndpoint(DummyEndpoint, PaginatedEndpoint):
    next: typing.Optional[str] = None
    prev: typing.Optional[str] = None
    first: typing.Optional[str] = None
    last: typing.Optional[str] = None

    def get_next(self) -> typing.Optional[str]:
        return self.next

    def get_prev(self) -> typing.Optional[str]:
        return self.prev

    def get_first(self) -> typing.Optional[str]:
        return self.first

    def get_last(self) -> typing.Optional[str]:
        return self.last


class PlainInfoExtractor(InfoExtractor):
    def extract_descriptor_name_for_serde(self, native_descr: NativeDescriptor) -> str:
        return native_descr.class_.__name__.lower()

    def extract_attribute_name_for_serde(self, native_attr_descr: NativeAttributeDescriptor) -> str:
        return assert_not_none(native_attr_descr.name)

    def extract_attribute_type_for_serde(
        self, native_attr_descr: NativeAttributeDescriptor
    ) -> typing.Type:
        return assert_not_none(native_attr_descr.type)

    def extract_attribute_flags_for_serde(
        self, native_attr_descr: NativeAttributeDescriptor
    ) -> AttributeFlags:
        retval: AttributeFlags = AttributeFlags.NONE
        if native_attr_descr.allow_null:
            retval |= AttributeFlags.ALLOW_NULL
        return retval

    def extract_relationship_name_for_serde(
        self, native_rel_descr: NativeRelationshipDescriptor
    ) -> str:
        return assert_not_none(native_rel_descr.name)
