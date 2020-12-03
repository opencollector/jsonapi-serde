import dataclasses
import typing
from unittest import mock

import pytest

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
from ..models import (
    ResourceAttributeDescriptor,
    ResourceDescriptor,
    ResourceToManyRelationshipDescriptor,
    ResourceToOneRelationshipDescriptor,
)
from ..serde.builders import (
    ResourceReprBuilder,
    ToManyRelDocumentBuilder,
    ToOneRelDocumentBuilder,
)
from ..serde.models import (
    AttributeValue,
    LinkageRepr,
    LinksRepr,
    ResourceIdRepr,
    ResourceRepr,
    Source,
    ToManyRelDocumentRepr,
    ToOneRelDocumentRepr,
)


@dataclasses.dataclass
class Foo:
    a: str
    b: int
    c: int
    bar: typing.Optional["Bar"] = None
    bazs: typing.Optional[typing.Sequence["Baz"]] = None
    id: typing.Optional[int] = None


@dataclasses.dataclass
class Bar:
    d: typing.Optional[str]
    e: int
    id: typing.Optional[int] = None


@dataclasses.dataclass
class Baz:
    f: int
    g: str
    id: typing.Optional[int] = None


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


class TestMapper:
    @pytest.fixture
    def bar_resource_descr(self):
        return ResourceDescriptor(
            name="bar",
            attributes=[
                ResourceAttributeDescriptor(
                    name="d",
                    type=str,
                    allow_null=True,
                ),
                ResourceAttributeDescriptor(
                    name="e",
                    type=int,
                    allow_null=False,
                ),
            ],
            relationships=[],
        )

    @pytest.fixture
    def bar_native_descr(self):
        return PlainNativeDescriptor(
            Bar,
            attributes=[
                PlainNativeAttributeDescriptor("d", str, True),
                PlainNativeAttributeDescriptor("e", int, False),
            ],
        )

    @pytest.fixture
    def baz_resource_descr(self):
        return ResourceDescriptor(
            name="baz",
            attributes=[
                ResourceAttributeDescriptor(
                    name="f",
                    type=int,
                    allow_null=True,
                ),
                ResourceAttributeDescriptor(
                    name="g",
                    type=str,
                    allow_null=False,
                ),
            ],
            relationships=[],
        )

    @pytest.fixture
    def baz_native_descr(self):
        return PlainNativeDescriptor(
            Baz,
            attributes=[
                PlainNativeAttributeDescriptor("f", int, True),
                PlainNativeAttributeDescriptor("g", str, False),
            ],
        )

    @pytest.fixture
    def resource_descr(
        self, bar_resource_descr: ResourceDescriptor, baz_resource_descr: ResourceDescriptor
    ):
        return ResourceDescriptor(
            name="foo",
            attributes=[
                ResourceAttributeDescriptor(
                    name="a",
                    type=str,
                    allow_null=False,
                ),
                ResourceAttributeDescriptor(
                    name="b",
                    type=int,
                    allow_null=True,
                ),
                ResourceAttributeDescriptor(
                    name="c",
                    type=int,
                    allow_null=False,
                ),
            ],
            relationships=[
                ResourceToOneRelationshipDescriptor(bar_resource_descr, "bar"),
                ResourceToManyRelationshipDescriptor(baz_resource_descr, "bazs"),
            ],
        )

    @pytest.fixture
    def native_descr(self, bar_native_descr, baz_native_descr):
        return PlainNativeDescriptor(
            class_=Foo,
            attributes=[
                PlainNativeAttributeDescriptor("a", str, False),
                PlainNativeAttributeDescriptor("b", int, True),
                PlainNativeAttributeDescriptor("c", int, False),
            ],
            relationships=[
                PlainNativeToOneRelationshipDescriptor(bar_native_descr, "bar"),
                PlainNativeToManyRelationshipDescriptor(baz_native_descr, "bazs"),
            ],
        )

    @pytest.fixture
    def target(self, resource_descr, native_descr, identity_mapping_pair):
        from ..mapper import Mapper, RelationshipMapping, ToOneAttributeMapping

        return Mapper[Foo](
            resource_descr,
            native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    resource_descr.attributes[na.name], na, *identity_mapping_pair
                )
                for na in native_descr.attributes
            ],
            relationship_mappings=[
                RelationshipMapping(resource_descr.relationships[nr.name], nr)
                for nr in native_descr.relationships
            ],
        )

    @pytest.fixture
    def bar_mapper(self, bar_resource_descr, bar_native_descr, identity_mapping_pair):
        from ..mapper import Mapper, RelationshipMapping, ToOneAttributeMapping

        return Mapper[Bar](
            bar_resource_descr,
            bar_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](ra, na, *identity_mapping_pair)
                for ra, na in zip(bar_resource_descr.attributes, bar_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(bar_resource_descr.relationships, bar_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def baz_mapper(self, baz_resource_descr, baz_native_descr, identity_mapping_pair):
        from ..mapper import Mapper, RelationshipMapping, ToOneAttributeMapping

        return Mapper[Baz](
            baz_resource_descr,
            baz_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](ra, na, *identity_mapping_pair)
                for ra, na in zip(baz_resource_descr.attributes, baz_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(baz_resource_descr.relationships, baz_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def dummy_to_native_context(
        self, bar_mapper, bar_resource_descr, baz_mapper, baz_resource_descr
    ):
        from ..mapper import (
            AttributeMapping,
            Mapper,
            RelationshipMapping,
            ToNativeContext,
        )

        class DummyToNativeContext(ToNativeContext):
            def query_mapper_by_serde(self, descr: ResourceDescriptor) -> Mapper:
                if descr is bar_resource_descr:
                    return bar_mapper
                elif descr is baz_resource_descr:
                    return baz_mapper
                else:
                    raise AssertionError()

            def query_descriptor_by_type_name(self, name: str) -> ResourceDescriptor:
                if bar_resource_descr.name == name:
                    return bar_resource_descr
                elif baz_resource_descr.name == name:
                    return baz_resource_descr
                else:
                    raise AssertionError()

            def select_attribute(self, mapping: AttributeMapping):
                return True

            def select_relationship(self, mapping: RelationshipMapping) -> bool:
                return True

            def get_native_identity_by_serde(
                self, mapper: Mapper, repr: typing.Union[ResourceRepr, ResourceIdRepr]
            ) -> typing.Any:
                return repr.id

        return DummyToNativeContext()

    @pytest.fixture
    def identity_mapping_pair(self):
        from ..mapper import ToNativeContext, ToSerdeContext

        def to_serde_identity_mapping(ctx: ToSerdeContext, value: typing.Any) -> AttributeValue:
            return typing.cast(AttributeValue, value)

        def to_native_identity_mapping(
            ctx: ToNativeContext, source: Source, value: AttributeValue
        ) -> typing.Any:
            return value

        return to_serde_identity_mapping, to_native_identity_mapping

    def test_create_from_serde(
        self,
        target,
        bar_mapper,
        bar_resource_descr,
        baz_mapper,
        baz_resource_descr,
        dummy_to_native_context,
    ):
        class DummyMutationContext(PlainMutationContext):
            def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
                if descr is bar_mapper.native_descr:
                    return Bar(id=id, d=None, e=1)
                elif descr is baz_mapper.native_descr:
                    return Baz(id=id, f=3, g="4")
                raise AssertionError()

        serde = ResourceRepr(
            type="foo",
            id="1",
            attributes=[
                ("a", "1"),
                ("b", None),
                ("c", 3),
            ],
            relationships=[
                (
                    "bar",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foos/1/relationships/bar",
                            related="/bars/1",
                        ),
                        data=ResourceIdRepr(
                            type="bar",
                            id="1",
                        ),
                    ),
                ),
                (
                    "bazs",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foos/1/relationships/bazs",
                            related="/bazs/1",
                        ),
                        data=[
                            ResourceIdRepr(
                                type="baz",
                                id="1",
                            ),
                            ResourceIdRepr(
                                type="baz",
                                id="2",
                            ),
                        ],
                    ),
                ),
            ],
        )

        result = target.create_from_serde(dummy_to_native_context, DummyMutationContext(), serde)
        assert isinstance(result, Foo)
        assert result.a == "1"
        assert result.b is None
        assert result.c == 3
        assert result.bar.id == "1"
        assert len(result.bazs) == 2
        assert result.bazs[0].id == "1"
        assert result.bazs[1].id == "2"

    def test_update_with_serde(
        self,
        target,
        bar_mapper,
        bar_resource_descr,
        baz_mapper,
        baz_resource_descr,
        dummy_to_native_context,
    ):
        class DummyMutationContext(PlainMutationContext):
            def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
                if descr is bar_mapper.native_descr:
                    return Bar(id=id, d="1", e=1)
                elif descr is baz_mapper.native_descr:
                    return Baz(id=id, f=3, g="4")
                raise AssertionError()

        serde = ResourceRepr(
            type="foo",
            id="1",
            attributes=[
                ("a", "1"),
                ("b", 2),
                ("c", 3),
            ],
            relationships=[
                (
                    "bar",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foos/1/relationships/bar",
                            related="/bars/1",
                        ),
                        data=ResourceIdRepr(
                            type="bar",
                            id="1",
                        ),
                    ),
                ),
                (
                    "bazs",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foos/1/relationships/bazs",
                            related="/bazs/1",
                        ),
                        data=[
                            ResourceIdRepr(
                                type="baz",
                                id="1",
                            ),
                            ResourceIdRepr(
                                type="baz",
                                id="2",
                            ),
                        ],
                    ),
                ),
            ],
        )

        obj = Foo(id=1, a="2", b=3, c=4, bar=None, bazs=[])

        result = target.update_with_serde(
            dummy_to_native_context, DummyMutationContext(), obj, serde
        )
        assert isinstance(result, Foo)
        assert result.a == "1"
        assert result.b == 2
        assert result.c == 3
        assert result.bar.id == "1"
        assert len(result.bazs) == 2
        assert result.bazs[0].id == "1"
        assert result.bazs[1].id == "2"

    @pytest.fixture
    def dummy_to_serde_context(
        self, target, bar_mapper, bar_native_descr, baz_mapper, baz_native_descr
    ):
        from ..mapper import (
            AttributeMapping,
            Mapper,
            RelationshipMapping,
            ToSerdeContext,
        )

        class SelectRelationship(typing.Protocol):
            def __call__(self, mapping: RelationshipMapping) -> bool:
                ...  # pragma: nocover

        class DummyToSerdeContext(ToSerdeContext):
            _select_relationship: SelectRelationship

            def select_attribute(self, mapping: AttributeMapping):
                return True

            def select_relationship(self, mapping: RelationshipMapping):
                return self._select_relationship(mapping)

            def get_serde_identity_by_native(self, mapper: Mapper, native: typing.Any) -> str:
                return str(native.id)

            def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
                return descr.name

            def resolve_to_one_relationship_endpoint(
                self,
                mapper: "Mapper",
                native_descr: NativeToOneRelationshipDescriptor,
                rel_descr: ResourceToOneRelationshipDescriptor,
                native: typing.Any,
            ) -> Endpoint:
                return DummyEndpoint(
                    self_=(
                        f"/{mapper.resource_descr.name}/{native.id}/"
                        f"@{rel_descr.destination.name}/{native_descr.fetch_related(native).id}"
                    )
                )

            def resolve_to_many_relationship_endpoint(
                self,
                mapper: "Mapper",
                native_descr: NativeToManyRelationshipDescriptor,
                rel_descr: ResourceToManyRelationshipDescriptor,
                native: typing.Any,
            ) -> PaginatedEndpoint:
                return DummyPaginatedEndpoint(
                    self_=(
                        f"/{mapper.resource_descr.name}/{native.id}/"
                        f"@{rel_descr.destination.name}?page=0"
                    ),
                    next=(
                        f"/{mapper.resource_descr.name}/{native.id}/"
                        f"@{rel_descr.destination.name}?page=1"
                    ),
                )

            def query_mapper_by_native(self, descr: NativeDescriptor) -> Mapper:
                if descr is bar_native_descr:
                    return bar_mapper
                elif descr is baz_native_descr:
                    return baz_mapper
                else:
                    raise AssertionError()

            def __init__(self, select_relationship: SelectRelationship):
                self._select_relationship = select_relationship

        return DummyToSerdeContext

    def test_build_serde(self, target, dummy_to_serde_context):
        builder = ResourceReprBuilder()
        native = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=Bar(
                d="1",
                e=2,
                id="1",
            ),
            bazs=[
                Baz(f=1, g="2", id="1"),
                Baz(f=3, g="4", id="2"),
            ],
        )
        dummy_serde_builder_context = mock.Mock()
        target.build_serde(
            dummy_to_serde_context(lambda _: True), dummy_serde_builder_context, builder, native
        )
        assert builder() == ResourceRepr(
            type="foo",
            id="1",
            links=None,
            attributes=(
                ("a", "1"),
                ("b", 2),
                ("c", 3),
            ),
            relationships=(
                (
                    "bar",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foo/1/@bar/1",
                        ),
                        data=ResourceIdRepr(
                            type="bar",
                            id="1",
                        ),
                    ),
                ),
                (
                    "bazs",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foo/1/@baz?page=0",
                            next="/foo/1/@baz?page=1",
                        ),
                        data=(
                            ResourceIdRepr(
                                type="baz",
                                id="1",
                            ),
                            ResourceIdRepr(
                                type="baz",
                                id="2",
                            ),
                        ),
                    ),
                ),
            ),
        )

    def test_build_serde_omit_relationship(
        self,
        target,
        bar_mapper,
        bar_native_descr,
        baz_mapper,
        baz_native_descr,
        dummy_to_serde_context,
    ):
        builder = ResourceReprBuilder()
        native = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=Bar(
                d="1",
                e=2,
                id="1",
            ),
            bazs=[
                Baz(f=1, g="2", id="1"),
                Baz(f=3, g="4", id="2"),
            ],
        )
        dummy_serde_builder_context = mock.Mock()
        target.build_serde(
            dummy_to_serde_context(lambda mapping: mapping is target.relationship_mappings[1]),
            dummy_serde_builder_context,
            builder,
            native,
        )
        assert builder() == ResourceRepr(
            type="foo",
            id="1",
            links=None,
            attributes=(
                ("a", "1"),
                ("b", 2),
                ("c", 3),
            ),
            relationships=(
                (
                    "bazs",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foo/1/@baz?page=0",
                            next="/foo/1/@baz?page=1",
                        ),
                        data=(
                            ResourceIdRepr(
                                type="baz",
                                id="1",
                            ),
                            ResourceIdRepr(
                                type="baz",
                                id="2",
                            ),
                        ),
                    ),
                ),
            ),
        )

    def test_build_serde_to_one_relationship(self, target, dummy_to_serde_context):
        builder = ToOneRelDocumentBuilder()
        native = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=Bar(
                d="1",
                e=2,
                id="1",
            ),
        )
        dummy_serde_builder_context = mock.Mock()
        target.build_serde_to_one_relationship(
            dummy_to_serde_context(lambda _: True),
            dummy_serde_builder_context,
            builder,
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
        )
        assert builder() == ToOneRelDocumentRepr(
            links=LinksRepr(
                self_="/foo/1/@bar/1",
            ),
            data=ResourceIdRepr(
                type="bar",
                id="1",
            ),
        )

    def test_build_serde_to_many_relationship(self, target, dummy_to_serde_context):
        builder = ToManyRelDocumentBuilder()
        native = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bazs=[
                Baz(f=1, g="2", id="1"),
                Baz(f=3, g="4", id="2"),
            ],
        )
        dummy_serde_builder_context = mock.Mock()
        target.build_serde_to_many_relationship(
            dummy_to_serde_context(lambda _: True),
            dummy_serde_builder_context,
            builder,
            native,
            target.get_relationship_mapping_by_serde_name(None, "bazs"),
        )
        assert builder() == ToManyRelDocumentRepr(
            links=LinksRepr(
                self_="/foo/1/@baz?page=0",
                next="/foo/1/@baz?page=1",
            ),
            data=(
                ResourceIdRepr(
                    type="baz",
                    id="1",
                ),
                ResourceIdRepr(
                    type="baz",
                    id="2",
                ),
            ),
        )
