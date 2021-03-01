import dataclasses
import typing

from ..declarative import AttributeFlags, InfoExtractor, RelationshipFlags
from ..deferred import Deferred, Promise
from ..exceptions import NativeAttributeNotFoundError, NativeRelationshipNotFoundError
from ..interfaces import (
    Endpoint,
    MutationContext,
    MutatorDescriptor,
    NativeAttributeDescriptor,
    NativeBuilder,
    NativeDescriptor,
    NativeRelationshipDescriptor,
    NativeToManyRelationshipBuilder,
    NativeToManyRelationshipDescriptor,
    NativeToManyRelationshipManipulator,
    NativeToOneRelationshipBuilder,
    NativeToOneRelationshipDescriptor,
    NativeToOneRelationshipManipulator,
    NativeUpdater,
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

    def store_value(self, target: typing.Any, value: typing.Any) -> bool:
        prev_value = getattr(target, self._name)
        setattr(target, self._name, value)
        return value != prev_value

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


class PlainNativeToOneRelationshipBuilder(NativeToOneRelationshipBuilder):
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


class PlainNativeToManyRelationshipBuilder(NativeToManyRelationshipBuilder):
    descr: PlainNativeToManyRelationshipDescriptor
    _ids: typing.List[typing.Any]

    def next(self, id: typing.Any):
        self._ids.append(id)

    def __call__(self, ctx: MutationContext) -> typing.Sequence[typing.Any]:
        return self._ids

    def __init__(self, descr: PlainNativeToManyRelationshipDescriptor):
        self.descr = descr
        self._ids = []


class PlainBuilderBase:
    descr: "PlainNativeDescriptor"
    attrs: typing.Dict[PlainNativeAttributeDescriptor, typing.Any]
    relationships: typing.Dict[
        typing.Union[
            PlainNativeToOneRelationshipDescriptor, PlainNativeToManyRelationshipDescriptor
        ],
        typing.Union[NativeToOneRelationshipBuilder, NativeToManyRelationshipBuilder],
    ]
    immutables: typing.Dict[PlainNativeAttributeDescriptor, MutatorDescriptor]

    def __setitem__(self, descr: NativeAttributeDescriptor, v: typing.Any) -> None:
        assert isinstance(descr, PlainNativeAttributeDescriptor)
        self.attrs[descr] = v

    def mark_immutable(
        self, descr: NativeAttributeDescriptor, mutator_descr: MutatorDescriptor
    ) -> None:
        assert isinstance(descr, PlainNativeAttributeDescriptor)
        self.immutables[descr] = mutator_descr

    def to_one_relationship(
        self, rel_descr: NativeToOneRelationshipDescriptor
    ) -> NativeToOneRelationshipBuilder:
        assert isinstance(rel_descr, PlainNativeToOneRelationshipDescriptor)
        builder = PlainNativeToOneRelationshipBuilder(rel_descr)
        self.relationships[rel_descr] = builder
        return builder

    def to_many_relationship(
        self,
        rel_descr: NativeToManyRelationshipDescriptor,
    ) -> NativeToManyRelationshipBuilder:
        assert isinstance(rel_descr, PlainNativeToManyRelationshipDescriptor)
        builder = PlainNativeToManyRelationshipBuilder(rel_descr)
        self.relationships[rel_descr] = builder
        return builder

    def __init__(self, descr: "PlainNativeDescriptor"):
        self.descr = descr
        self.attrs = {}
        self.relationships = {}
        self.immutables = {}


class PlainBuilder(PlainBuilderBase, NativeBuilder):
    def __call__(self, ctx: MutationContext) -> typing.Any:
        assert isinstance(ctx, PlainMutationContext)
        attrs = {descr.name: v for descr, v in self.attrs.items() if descr.name is not None}
        rels = {}
        for descr, rb in self.relationships.items():
            if descr.name is None:
                continue
            if isinstance(rb, PlainNativeToOneRelationshipBuilder):
                id_ = rb(ctx)
                rels[descr.name] = (
                    ctx.query_by_identity(descr.destination, id=id_) if id_ is not None else None
                )
            elif isinstance(rb, PlainNativeToManyRelationshipBuilder):
                rels[descr.name] = [
                    ctx.query_by_identity(descr.destination, id_) for id_ in rb(ctx)
                ]
        return self.descr.class_(**attrs, **rels)

    def __init__(self, descr: "PlainNativeDescriptor"):
        super().__init__(descr)


class PlainNativeToOneRelationshipManipulator(NativeToOneRelationshipManipulator):
    descr: PlainNativeToOneRelationshipDescriptor
    promise: typing.Optional[Promise[bool]] = None
    unset_id: typing.Optional[typing.Any] = None
    set_id: typing.Optional[typing.Any] = None

    def nullify(self) -> Deferred[bool]:
        assert self.promise is None
        self.promise = Promise[bool]()
        return self.promise

    def unset(self, id: typing.Any) -> Deferred[bool]:
        assert self.promise is None
        self.unset_id = id
        self.promise = Promise[bool]()
        return self.promise

    def set(self, id: typing.Any) -> Deferred[bool]:
        assert self.promise is None
        self.set_id = id
        self.promise = Promise[bool]()
        return self.promise

    def __init__(self, descr: PlainNativeToOneRelationshipDescriptor):
        self.descr = descr


class PlainNativeToManyRelationshipManipulator(NativeToManyRelationshipManipulator):
    descr: PlainNativeToManyRelationshipDescriptor
    added: typing.List[typing.Tuple[typing.Any, Deferred[bool]]]
    removed: typing.Dict[typing.Any, Deferred[bool]]

    def add(self, id: typing.Any) -> Deferred[bool]:
        p = Promise[bool]()
        self.added.append((id, p))
        return p

    def remove(self, id: typing.Any) -> Deferred[bool]:
        p = Promise[bool]()
        self.removed[id] = p
        return p

    def __init__(self, descr: PlainNativeToManyRelationshipDescriptor):
        self.descr = descr
        self.added = []
        self.removed = {}


class PlainUpdater(PlainBuilderBase, NativeUpdater):
    obj: typing.Any
    to_one_manipulators: typing.Dict[
        PlainNativeToOneRelationshipDescriptor, PlainNativeToOneRelationshipManipulator
    ]
    to_many_manipulators: typing.Dict[
        PlainNativeToManyRelationshipDescriptor, PlainNativeToManyRelationshipManipulator
    ]

    def to_one_relationship_manipulator(
        self, descr: NativeToOneRelationshipDescriptor
    ) -> NativeToOneRelationshipManipulator:
        assert isinstance(descr, PlainNativeToOneRelationshipDescriptor)
        assert descr not in self.to_one_manipulators
        manip = PlainNativeToOneRelationshipManipulator(descr)
        self.to_one_manipulators[descr] = manip
        return manip

    def to_many_relationship_manipulator(
        self, descr: NativeToManyRelationshipDescriptor
    ) -> NativeToManyRelationshipManipulator:
        assert isinstance(descr, PlainNativeToManyRelationshipDescriptor)
        assert descr not in self.to_many_manipulators
        manip = PlainNativeToManyRelationshipManipulator(descr)
        self.to_many_manipulators[descr] = manip
        return manip

    def __call__(self, ctx: MutationContext) -> typing.Any:
        assert isinstance(ctx, PlainMutationContext)
        for descr, v in self.attrs.items():
            if descr.store_value(self.obj, v):
                mutator_descr = self.immutables.get(descr)
                if mutator_descr:
                    mutator_descr.raise_immutable_attribute_error()

        for rel_descr, rb in self.relationships.items():
            if isinstance(rb, PlainNativeToOneRelationshipBuilder):
                id_ = rb(ctx)
                rel_descr.replace_related(
                    self.obj,
                    (
                        ctx.query_by_identity(rel_descr.destination, id=id_)
                        if id_ is not None
                        else None
                    ),
                )
            elif isinstance(rb, PlainNativeToManyRelationshipBuilder):
                rel_descr.replace_related(
                    self.obj, (ctx.query_by_identity(rel_descr.destination, id_) for id_ in rb(ctx))
                )
        for to_one_manip in self.to_one_manipulators.values():
            if to_one_manip.promise is not None:
                if to_one_manip.unset_id is not None:
                    old_obj = to_one_manip.descr.fetch_related(self.obj)
                    old_id = (
                        to_one_manip.descr.destination.get_identity(old_obj)
                        if old_obj is not None
                        else None
                    )
                    if old_id == to_one_manip.unset_id:
                        to_one_manip.descr.replace_related(self.obj, None)
                        to_one_manip.promise.set(True)
                    else:
                        to_one_manip.promise.set(False)
                else:
                    if to_one_manip.set_id is not None:
                        new_rel = ctx.query_by_identity(
                            to_one_manip.descr.destination, to_one_manip.set_id
                        )
                    else:
                        new_rel = None
                    to_one_manip.descr.replace_related(self.obj, new_rel)
                    to_one_manip.promise.set(True)

        for to_many_manip in self.to_many_manipulators.values():
            rels = to_many_manip.descr.fetch_related(self.obj)
            remainder = dict(to_many_manip.removed)
            new_rels: typing.List[typing.Any] = []
            for rel in rels:
                id_ = to_many_manip.descr.destination.get_identity(rel)
                p = remainder.pop(id_, None)
                if p is not None:
                    p.set(True)  # type: ignore
                else:
                    new_rels.append(rel)
            for p in remainder.values():
                p.set(False)  # type: ignore
            for id_, p in to_many_manip.added:
                rel = ctx.query_by_identity(to_many_manip.descr.destination, id_)
                new_rels.append(rel)
                p.set(True)  # type: ignore
            to_many_manip.descr.replace_related(self.obj, new_rels)

        return self.obj

    def __init__(self, descr: "PlainNativeDescriptor", obj: typing.Any):
        super().__init__(descr)
        assert isinstance(obj, descr.class_)
        self.obj = obj
        self.to_one_manipulators = {}
        self.to_many_manipulators = {}


class PlainNativeDescriptor(NativeDescriptor):
    _class_: type
    _attributes: typing.Sequence[NativeAttributeDescriptor]
    _relationships: typing.Sequence[NativeRelationshipDescriptor]

    @property
    def class_(self) -> type:
        return self._class_

    def new_builder(self) -> NativeBuilder:
        return PlainBuilder(self)

    def new_updater(self, target: typing.Any) -> NativeUpdater:
        return PlainUpdater(self, target)

    @property
    def attributes(self) -> typing.Sequence[NativeAttributeDescriptor]:
        return self._attributes

    def get_attribute_by_name(self, name: str) -> NativeAttributeDescriptor:
        for descr in self._attributes:
            if descr.name == name:
                return descr
        raise NativeAttributeNotFoundError(self, name)

    @property
    def relationships(self) -> typing.Sequence[NativeRelationshipDescriptor]:
        return self._relationships

    def get_relationship_by_name(self, name: str) -> NativeRelationshipDescriptor:
        for descr in self._relationships:
            if descr.name == name:
                return descr
        raise NativeRelationshipNotFoundError(self, name)

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
    self_: typing.Optional[str]

    def get_self(self) -> typing.Optional[str]:
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

    def extract_relationship_flags_for_serde(
        self, native_rel_descr: NativeRelationshipDescriptor
    ) -> RelationshipFlags:
        return RelationshipFlags.NONE
