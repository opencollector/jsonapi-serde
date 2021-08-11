import dataclasses
import typing

import pytest

from ..exceptions import ImmutableAttributeError
from ..interfaces import (
    NativeDescriptor,
    NativeRelationshipDescriptor,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipDescriptor,
)
from ..models import (
    ResourceAttributeDescriptor,
    ResourceDescriptor,
    ResourceRelationshipDescriptor,
    ResourceToManyRelationshipDescriptor,
    ResourceToOneRelationshipDescriptor,
)
from ..serde.builders import (
    CollectionDocumentBuilder,
    ResourceReprBuilder,
    ToManyRelDocumentBuilder,
    ToManyRelReprBuilder,
    ToOneRelDocumentBuilder,
    ToOneRelReprBuilder,
)
from ..serde.models import (
    URL,
    AttributeValue,
    CollectionDocumentRepr,
    LinkageRepr,
    LinksRepr,
    ResourceIdRepr,
    ResourceRepr,
    Source,
    ToManyRelDocumentRepr,
    ToOneRelDocumentRepr,
)
from .testing import (
    PlainMutationContext,
    PlainNativeAttributeDescriptor,
    PlainNativeDescriptor,
    PlainNativeToManyRelationshipDescriptor,
    PlainNativeToOneRelationshipDescriptor,
)


@dataclasses.dataclass
class Foo:
    a: str
    b: int
    c: int
    bar: typing.Optional["Bar"] = None
    bazs: typing.Optional[typing.Sequence["Baz"]] = None
    id: typing.Optional[int] = None

    def __post_init__(self) -> None:
        if self.bar is not None:
            self.bar.foo = self
        if self.bazs is not None:
            for baz in self.bazs:
                baz.foo = self

    def __hash__(self):
        return id(self)


@dataclasses.dataclass
class Bar:
    d: typing.Optional[str]
    e: int
    foo: typing.Optional["Foo"] = None
    baz: typing.Optional["Baz"] = None
    id: typing.Optional[int] = None

    def __post_init__(self) -> None:
        if self.baz is not None:
            self.baz.bar = self

    def __hash__(self):
        return id(self)


@dataclasses.dataclass
class Baz:
    f: int
    g: str
    foo: typing.Optional[Foo] = None
    bar: typing.Optional[Bar] = None
    id: typing.Optional[int] = None

    def __post_init__(self) -> None:
        if self.bar is not None:
            self.bar.baz = self

    def __hash__(self):
        return id(self)


class TestMapperBase:
    @pytest.fixture
    def bar_resource_descr(self, baz_resource_descr) -> ResourceDescriptor:
        bar_resource_descr = ResourceDescriptor(
            name="bar",
            attributes=[
                ResourceAttributeDescriptor(
                    name="d",
                    type=str,
                    allow_null=True,
                    required_on_creation=False,
                ),
                ResourceAttributeDescriptor(
                    name="e",
                    type=int,
                    allow_null=False,
                    required_on_creation=True,
                ),
            ],
            relationships=[
                ResourceToOneRelationshipDescriptor(
                    baz_resource_descr,
                    "baz",
                    allow_null=True,
                ),
            ],
        )
        baz_resource_descr.add_relationship(
            ResourceToOneRelationshipDescriptor(
                bar_resource_descr,
                "bar",
                allow_null=True,
            ),
        )
        return bar_resource_descr

    @pytest.fixture
    def bar_native_descr(self, baz_native_descr) -> PlainNativeDescriptor:
        bar_native_descr = PlainNativeDescriptor(
            Bar,
            attributes=[
                PlainNativeAttributeDescriptor("d", str, True),
                PlainNativeAttributeDescriptor("e", int, False),
            ],
            relationships=[
                PlainNativeToOneRelationshipDescriptor(
                    baz_native_descr,
                    "baz",
                    allow_null=True,
                ),
            ],
        )
        baz_native_descr._relationships.append(
            PlainNativeToOneRelationshipDescriptor(
                bar_native_descr,
                "bar",
                allow_null=True,
            ),
        )
        return bar_native_descr

    @pytest.fixture
    def baz_resource_descr(self):
        return ResourceDescriptor(
            name="baz",
            attributes=[
                ResourceAttributeDescriptor(
                    name="f",
                    type=int,
                    allow_null=True,
                    required_on_creation=False,
                ),
                ResourceAttributeDescriptor(
                    name="g",
                    type=str,
                    allow_null=False,
                    required_on_creation=True,
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
    def foo_resource_descr(
        self, bar_resource_descr: ResourceDescriptor, baz_resource_descr: ResourceDescriptor
    ):
        foo_resource_descr = ResourceDescriptor(
            name="foo",
            attributes=[
                ResourceAttributeDescriptor(
                    name="a",
                    type=str,
                    allow_null=False,
                    required_on_creation=True,
                ),
                ResourceAttributeDescriptor(
                    name="b",
                    type=int,
                    allow_null=True,
                    required_on_creation=False,
                ),
                ResourceAttributeDescriptor(
                    name="c",
                    type=int,
                    allow_null=False,
                    required_on_creation=True,
                    immutable=True,
                ),
            ],
            relationships=[
                ResourceToOneRelationshipDescriptor(
                    bar_resource_descr,
                    "bar",
                    allow_null=True,
                ),
                ResourceToManyRelationshipDescriptor(
                    baz_resource_descr,
                    "bazs",
                ),
            ],
        )
        bar_resource_descr.add_relationship(
            ResourceToOneRelationshipDescriptor(
                foo_resource_descr,
                "foo",
                allow_null=True,
            ),
        )
        baz_resource_descr.add_relationship(
            ResourceToOneRelationshipDescriptor(
                foo_resource_descr,
                "foo",
                allow_null=True,
            ),
        )
        return foo_resource_descr

    @pytest.fixture
    def foo_native_descr(self, bar_native_descr, baz_native_descr):
        foo_native_descr = PlainNativeDescriptor(
            class_=Foo,
            attributes=[
                PlainNativeAttributeDescriptor("a", str, False),
                PlainNativeAttributeDescriptor("b", int, True),
                PlainNativeAttributeDescriptor("c", int, False),
            ],
            relationships=[
                PlainNativeToOneRelationshipDescriptor(
                    bar_native_descr,
                    "bar",
                    allow_null=True,
                ),
                PlainNativeToManyRelationshipDescriptor(
                    baz_native_descr,
                    "bazs",
                ),
            ],
        )
        bar_native_descr._relationships.append(
            PlainNativeToOneRelationshipDescriptor(
                foo_native_descr,
                "foo",
                allow_null=True,
            ),
        )
        baz_native_descr._relationships.append(
            PlainNativeToOneRelationshipDescriptor(
                foo_native_descr,
                "foo",
                allow_null=True,
            ),
        )
        return foo_native_descr

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


class TestMapper(TestMapperBase):
    @pytest.fixture
    def foo_mapper(self, foo_resource_descr, foo_native_descr, identity_mapping_pair):
        from ..mapper import (
            Direction,
            Mapper,
            RelationshipMapping,
            ToOneAttributeMapping,
        )

        return Mapper[Foo](
            foo_resource_descr,
            foo_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    serde_side=foo_resource_descr.attributes[na.name],
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
                )
                for na in foo_native_descr.attributes
            ],
            relationship_mappings=[
                RelationshipMapping(foo_resource_descr.relationships[nr.name], nr)
                for nr in foo_native_descr.relationships
            ],
        )

    @pytest.fixture
    def bar_mapper(
        self,
        bar_resource_descr,
        bar_native_descr,
        foo_resource_descr,
        foo_native_descr,
        identity_mapping_pair,
    ):
        from ..mapper import (
            Direction,
            Mapper,
            RelationshipMapping,
            ToOneAttributeMapping,
        )

        return Mapper[Bar](
            bar_resource_descr,
            bar_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    serde_side=bar_resource_descr.attributes[na.name],
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
                )
                for na in bar_native_descr.attributes
            ],
            relationship_mappings=[
                RelationshipMapping(bar_resource_descr.relationships[nr.name], nr)
                for nr in bar_native_descr.relationships
            ],
        )

    @pytest.fixture
    def baz_mapper(
        self,
        baz_resource_descr,
        baz_native_descr,
        foo_resource_descr,
        foo_native_descr,
        identity_mapping_pair,
    ):
        from ..mapper import (
            Direction,
            Mapper,
            RelationshipMapping,
            ToOneAttributeMapping,
        )

        return Mapper[Baz](
            baz_resource_descr,
            baz_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    serde_side=baz_resource_descr.attributes[na.name],
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
                )
                for na in baz_native_descr.attributes
            ],
            relationship_mappings=[
                RelationshipMapping(baz_resource_descr.relationships[nr.name], nr)
                for nr in baz_native_descr.relationships
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
    def target(self, foo_mapper):
        return foo_mapper

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

    @pytest.mark.parametrize(
        ("obj", "raises"),
        [
            (Foo(id=1, a="2", b=3, c=3, bar=None, bazs=[]), None),
            (Foo(id=1, a="2", b=3, c=4, bar=None, bazs=[]), ImmutableAttributeError),
        ],
    )
    def test_update_with_serde(
        self,
        target,
        bar_mapper,
        bar_resource_descr,
        baz_mapper,
        baz_resource_descr,
        dummy_to_native_context,
        obj,
        raises,
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

        if raises is not None:
            with pytest.raises(raises):
                target.update_with_serde(
                    dummy_to_native_context, DummyMutationContext(), obj, serde
                )
        else:
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
        self,
        foo_mapper,
        foo_native_descr,
        bar_mapper,
        bar_native_descr,
        baz_mapper,
        baz_native_descr,
    ):
        from ..mapper import (
            AttributeMapping,
            Mapper,
            PaginatedEndpoint,
            RelationshipMapping,
            RelationshipPart,
            ToSerdeContext,
        )

        class SelectRelationship(typing.Protocol):
            def __call__(self, mapping: RelationshipMapping) -> RelationshipPart:
                ...  # pragma: nocover

        class DummyToSerdeContext(ToSerdeContext):
            _select_relationship: SelectRelationship

            def select_attribute(self, mapping: AttributeMapping):
                return True

            def select_relationship(self, mapping: RelationshipMapping) -> RelationshipPart:
                return self._select_relationship(mapping)

            def get_serde_identity_by_native(self, mapper: Mapper, native: typing.Any) -> str:
                return str(native.id)

            def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
                return descr.name

            def resolve_singleton_endpoint(
                self, mapper: Mapper, native: typing.Any
            ) -> typing.Optional[URL]:
                return URL.from_string(f"/{mapper.resource_descr.name}/{native.id}/")

            def resolve_collection_endpoint(
                self, mapper: Mapper, natives: typing.Iterable[typing.Any]
            ) -> typing.Optional[PaginatedEndpoint]:
                return PaginatedEndpoint(self_=URL.from_string(f"/{mapper.resource_descr.name}/"))

            def resolve_to_one_relationship_endpoint(
                self,
                mapper: Mapper,
                native_descr: NativeToOneRelationshipDescriptor,
                rel_descr: ResourceToOneRelationshipDescriptor,
                native: typing.Any,
            ) -> URL:
                return URL.from_string(
                    f"/{mapper.resource_descr.name}/{native.id}/" f"@{rel_descr.destination.name}/"
                )

            def resolve_to_many_relationship_endpoint(
                self,
                mapper: Mapper,
                native_descr: NativeToManyRelationshipDescriptor,
                rel_descr: ResourceToManyRelationshipDescriptor,
                native: typing.Any,
            ) -> PaginatedEndpoint:
                return PaginatedEndpoint(
                    self_=URL.from_string(
                        f"/{mapper.resource_descr.name}/{native.id}/"
                        f"@{rel_descr.destination.name}?page[number]=0"
                    ),
                    next=URL.from_string(
                        f"/{mapper.resource_descr.name}/{native.id}/"
                        f"@{rel_descr.destination.name}?page[number]=1"
                    ),
                )

            def query_mapper_by_native(self, descr: NativeDescriptor) -> Mapper:
                if descr is bar_native_descr:
                    return bar_mapper
                elif descr is baz_native_descr:
                    return baz_mapper
                elif descr is foo_native_descr:
                    return foo_mapper
                else:
                    raise AssertionError()

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
                return

            def to_many_relationship_visited(
                self,
                native_side: NativeToManyRelationshipDescriptor,
                serde_side: ResourceToManyRelationshipDescriptor,
                mapper: "Mapper",
                dest_mapper: "Mapper",
                native: typing.Any,
                dest: typing.Optional[typing.Iterable[typing.Any]],
            ) -> None:
                return

            def native_visited_pre(
                self,
                mapper: "Mapper",
                native: typing.Any,
                as_rel_ref: bool,
            ) -> None:
                return

            def native_visited(
                self,
                mapper: "Mapper",
                native: typing.Any,
                as_rel_ref: bool,
            ) -> None:
                return

            def __init__(self, select_relationship: SelectRelationship):
                self._select_relationship = select_relationship

        return DummyToSerdeContext

    def test_build_serde(self, target, dummy_to_serde_context):
        from ..mapper import RelationshipPart

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
        target.build_serde(
            dummy_to_serde_context(lambda _: RelationshipPart.ALL),
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
                    "bar",
                    LinkageRepr(
                        links=LinksRepr(
                            self_=URL.from_string("/foo/1/@bar/"),
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
                            self_=URL.from_string("/foo/1/@baz?page[number]=0"),
                            next=URL.from_string("/foo/1/@baz?page[number]=1"),
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

    def test_build_serde_collection(self, target, dummy_to_serde_context):
        from ..mapper import RelationshipPart

        builder = CollectionDocumentBuilder()
        natives = [
            Foo(
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
            ),
            Foo(
                a="2",
                b=3,
                c=4,
                id="2",
                bar=Bar(
                    d="2",
                    e=3,
                    id="2",
                ),
                bazs=[
                    Baz(f=2, g="3", id="3"),
                    Baz(f=4, g="5", id="4"),
                ],
            ),
        ]
        target.build_serde_collection(
            dummy_to_serde_context(lambda _: RelationshipPart.ALL),
            builder,
            natives,
        )
        assert builder() == CollectionDocumentRepr(
            links=LinksRepr(
                self_=URL.from_string("/foo/"),
            ),
            data=(
                ResourceRepr(
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
                                    self_=URL.from_string("/foo/1/@bar/"),
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
                                    self_=URL.from_string("/foo/1/@baz?page[number]=0"),
                                    next=URL.from_string("/foo/1/@baz?page[number]=1"),
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
                ),
                ResourceRepr(
                    type="foo",
                    id="2",
                    links=None,
                    attributes=(
                        ("a", "2"),
                        ("b", 3),
                        ("c", 4),
                    ),
                    relationships=(
                        (
                            "bar",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_=URL.from_string("/foo/2/@bar/"),
                                ),
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="2",
                                ),
                            ),
                        ),
                        (
                            "bazs",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_=URL.from_string("/foo/2/@baz?page[number]=0"),
                                    next=URL.from_string("/foo/2/@baz?page[number]=1"),
                                ),
                                data=(
                                    ResourceIdRepr(
                                        type="baz",
                                        id="3",
                                    ),
                                    ResourceIdRepr(
                                        type="baz",
                                        id="4",
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )

    def test_build_serde_collection_traversing(self, baz_mapper, dummy_to_serde_context):
        from ..mapper import RelationshipPart

        builder = CollectionDocumentBuilder()
        bazs = [
            Baz(f=1, g="2", id="1"),
            Baz(f=3, g="4", id="2"),
        ]
        bars = [
            Bar(
                d="1",
                e=2,
                id="1",
                baz=bazs[0],
            ),
            Bar(
                d="1",
                e=2,
                id="2",
                baz=bazs[1],
            ),
        ]
        foo = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=bars[0],
            bazs=bazs,
        )
        assert bazs[0].foo is foo
        assert bazs[1].foo is foo
        assert bazs[0].bar.baz is bazs[0]
        assert bazs[1].bar.baz is bazs[1]

        baz_mapper.build_serde_collection(
            dummy_to_serde_context(lambda _: RelationshipPart.ALL),
            builder,
            bazs,
        )
        assert builder() == CollectionDocumentRepr(
            links=LinksRepr(
                self_=URL.from_string("/baz/"),
            ),
            data=(
                ResourceRepr(
                    type="baz",
                    id="1",
                    links=None,
                    attributes=(
                        ("f", 1),
                        ("g", "2"),
                    ),
                    relationships=(
                        (
                            "bar",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_=URL.from_string("/baz/1/@bar/"),
                                ),
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="1",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_=URL.from_string("/baz/1/@foo/"),
                                ),
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
                            ),
                        ),
                    ),
                ),
                ResourceRepr(
                    type="baz",
                    id="2",
                    links=None,
                    attributes=(
                        ("f", 3),
                        ("g", "4"),
                    ),
                    relationships=(
                        (
                            "bar",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_=URL.from_string("/baz/2/@bar/"),
                                ),
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="2",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_=URL.from_string("/baz/2/@foo/"),
                                ),
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
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
        from ..mapper import RelationshipPart

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
                baz=None,
            ),
            bazs=[
                Baz(f=1, g="2", id="1"),
                Baz(f=3, g="4", id="2"),
            ],
        )
        target.build_serde(
            dummy_to_serde_context(
                lambda mapping: (
                    RelationshipPart.ALL
                    if mapping is target.relationship_mappings[1]
                    else RelationshipPart.NONE
                )
            ),
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
                            self_=URL.from_string("/foo/1/@baz?page[number]=0"),
                            next=URL.from_string("/foo/1/@baz?page[number]=1"),
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

    @pytest.mark.parametrize(
        ("expected", "builder_class", "parts"),
        [
            (
                ToOneRelDocumentRepr(
                    data=ResourceIdRepr(
                        type="bar",
                        id="1",
                    ),
                ),
                ToOneRelDocumentBuilder,
                lambda RelationshipPart: RelationshipPart.DATA,
            ),
            (
                ToOneRelDocumentRepr(
                    links=LinksRepr(
                        self_=URL.from_string("/foo/1/@bar/"),
                    ),
                    data=ResourceIdRepr(
                        type="bar",
                        id="1",
                    ),
                ),
                ToOneRelDocumentBuilder,
                lambda RelationshipPart: RelationshipPart.ALL,
            ),
            (
                LinkageRepr(
                    links=LinksRepr(
                        self_=URL.from_string("/foo/1/@bar/"),
                    ),
                ),
                ToOneRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.LINKS,
            ),
            (
                LinkageRepr(
                    data=ResourceIdRepr(
                        type="bar",
                        id="1",
                    ),
                ),
                ToOneRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.DATA,
            ),
            (
                LinkageRepr(
                    links=LinksRepr(
                        self_=URL.from_string("/foo/1/@bar/"),
                    ),
                    data=ResourceIdRepr(
                        type="bar",
                        id="1",
                    ),
                ),
                ToOneRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.ALL,
            ),
        ],
    )
    def test_build_serde_to_one_relationship(
        self, target, dummy_to_serde_context, expected, builder_class, parts
    ):
        from ..mapper import RelationshipPart

        builder = builder_class()
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
        target.build_serde_to_one_relationship(
            dummy_to_serde_context(lambda _: RelationshipPart.ALL),
            builder,
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
            parts(RelationshipPart),
        )
        assert builder() == expected

    @pytest.mark.parametrize(
        ("expected", "builder_class", "parts"),
        [
            (
                ToOneRelDocumentRepr(
                    links=LinksRepr(self_=URL.from_string("/foo/1/@bar/")),
                    data=None,
                ),
                ToOneRelDocumentBuilder,
                lambda RelationshipPart: RelationshipPart.ALL,
            ),
            (
                ToOneRelDocumentRepr(
                    data=None,
                ),
                ToOneRelDocumentBuilder,
                lambda RelationshipPart: RelationshipPart.DATA,
            ),
            (
                LinkageRepr(
                    links=LinksRepr(self_=URL.from_string("/foo/1/@bar/")),
                ),
                ToOneRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.LINKS,
            ),
            (
                LinkageRepr(
                    data=None,
                ),
                ToOneRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.DATA,
            ),
            (
                LinkageRepr(
                    links=LinksRepr(self_=URL.from_string("/foo/1/@bar/")),
                    data=None,
                ),
                ToOneRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.ALL,
            ),
        ],
    )
    def test_build_serde_to_one_relationship_none(
        self, target, dummy_to_serde_context, expected, builder_class, parts
    ):
        from ..mapper import RelationshipPart

        builder = builder_class()
        native = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=None,
        )
        target.build_serde_to_one_relationship(
            dummy_to_serde_context(lambda _: RelationshipPart.ALL),
            builder,
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
            parts(RelationshipPart),
        )
        assert builder() == expected

    @pytest.mark.parametrize(
        ("expected", "builder_class", "parts"),
        [
            (
                ToManyRelDocumentRepr(
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
                ToManyRelDocumentBuilder,
                lambda RelationshipPart: RelationshipPart.DATA,
            ),
            (
                ToManyRelDocumentRepr(
                    links=LinksRepr(
                        self_=URL.from_string("/foo/1/@baz?page[number]=0"),
                        next=URL.from_string("/foo/1/@baz?page[number]=1"),
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
                ToManyRelDocumentBuilder,
                lambda RelationshipPart: RelationshipPart.ALL,
            ),
            (
                LinkageRepr(
                    links=LinksRepr(
                        self_=URL.from_string("/foo/1/@baz?page[number]=0"),
                        next=URL.from_string("/foo/1/@baz?page[number]=1"),
                    ),
                ),
                ToManyRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.LINKS,
            ),
            (
                LinkageRepr(
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
                ToManyRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.DATA,
            ),
            (
                LinkageRepr(
                    links=LinksRepr(
                        self_=URL.from_string("/foo/1/@baz?page[number]=0"),
                        next=URL.from_string("/foo/1/@baz?page[number]=1"),
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
                ToManyRelReprBuilder,
                lambda RelationshipPart: RelationshipPart.ALL,
            ),
        ],
    )
    def test_build_serde_to_many_relationship(
        self, target, dummy_to_serde_context, expected, builder_class, parts
    ):
        from ..mapper import RelationshipPart

        builder = builder_class()
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
        target.build_serde_to_many_relationship(
            dummy_to_serde_context(lambda _: RelationshipPart.ALL),
            builder,
            native,
            target.get_relationship_mapping_by_serde_name(None, "bazs"),
            parts(RelationshipPart),
        )
        assert builder() == expected

    def test_update_to_one_rel_with_serde(self, target, bar_mapper, dummy_to_native_context):
        class DummyMutationContext(PlainMutationContext):
            def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
                if descr is bar_mapper.native_descr:
                    return Bar(id=id, d="2", e=3)
                raise AssertionError()

        native = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=Bar(d="1", e=2, id="1"),
        )
        serde = ResourceIdRepr(type="bar", id="3")
        result = target.update_to_one_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
            serde,
        )
        assert result.bar == Bar(d="2", e=3, id="3")

        native = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=Bar(d="1", e=2, id="1"),
        )
        result = target.update_to_one_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
            None,
        )
        assert result.bar is None

    def test_update_to_many_rel_with_serde(self, target, baz_mapper, dummy_to_native_context):
        class DummyMutationContext(PlainMutationContext):
            def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
                if descr is baz_mapper.native_descr:
                    return Baz(id=id, f=5, g="6")
                raise AssertionError()

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
        serde = [
            ResourceIdRepr(type="baz", id="3"),
        ]
        result = target.update_to_many_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bazs"),
            serde,
        )
        assert result.bazs == [Baz(f=5, g="6", id="3")]

    def test_add_to_one_rel_with_serde(self, target, bar_mapper, dummy_to_native_context):
        class DummyMutationContext(PlainMutationContext):
            def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
                if descr is bar_mapper.native_descr:
                    return Bar(id=id, d="2", e=3)
                raise AssertionError()

        native = Foo(a="1", b=2, c=3, id="1", bar=None)
        serde = ResourceIdRepr(type="bar", id="3")
        result, changed = target.add_to_one_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
            serde,
        )
        assert changed
        assert result.bar == Bar(d="2", e=3, id="3")

    def test_remove_to_one_rel_with_serde(self, target, bar_mapper, dummy_to_native_context):
        class DummyMutationContext(PlainMutationContext):
            def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
                if descr is bar_mapper.native_descr:
                    return Bar(id=id, d="2", e=3)
                raise AssertionError()

        native = Foo(a="1", b=2, c=3, id="1", bar=None)
        serde = ResourceIdRepr(type="bar", id="3")
        result, changed = target.remove_to_one_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
            serde,
        )
        assert not changed
        assert result.bar is None

        native = Foo(a="1", b=2, c=3, id="1", bar=Bar(d="1", e=2, id="1"))
        serde = ResourceIdRepr(type="bar", id="3")
        result, changed = target.remove_to_one_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
            serde,
        )
        assert not changed
        assert result.bar is not None

        native = Foo(a="1", b=2, c=3, id="1", bar=Bar(d="1", e=2, id="1"))
        serde = ResourceIdRepr(type="bar", id="1")
        result, changed = target.remove_to_one_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bar"),
            serde,
        )
        assert changed
        assert result.bar is None

    def test_add_to_many_rel_with_serde(self, target, baz_mapper, dummy_to_native_context):
        class DummyMutationContext(PlainMutationContext):
            def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
                if descr is baz_mapper.native_descr:
                    return Baz(id=id, f=3, g="4")
                raise AssertionError()

        native = Foo(a="1", b=2, c=3, id="1", bar=None, bazs=[Baz(f=1, g="2", id="1")])
        result, changes = target.add_to_many_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bazs"),
            [
                ResourceIdRepr(type="baz", id="2"),
                ResourceIdRepr(type="baz", id="3"),
            ],
        )
        assert len(changes) == 2
        assert len(result.bazs) == 3
        assert changes == [
            (ResourceIdRepr(type="baz", id="2"), True),
            (ResourceIdRepr(type="baz", id="3"), True),
        ]

    def test_remove_to_many_rel_with_serde(self, target, baz_mapper, dummy_to_native_context):
        class DummyMutationContext(PlainMutationContext):
            def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
                if descr is baz_mapper.native_descr:
                    return Baz(id=id, f=3, g="4")
                raise AssertionError()

        native = Foo(a="1", b=2, c=3, id="1", bar=None, bazs=[Baz(f=1, g="2", id="1")])
        result, changes = target.remove_to_many_rel_with_serde(
            dummy_to_native_context,
            DummyMutationContext(),
            native,
            target.get_relationship_mapping_by_serde_name(None, "bazs"),
            [
                ResourceIdRepr(type="baz", id="2"),
                ResourceIdRepr(type="baz", id="3"),
            ],
        )
        assert len(changes) == 2
        assert len(result.bazs) == 1
        assert changes == [
            (ResourceIdRepr(type="baz", id="2"), False),
            (ResourceIdRepr(type="baz", id="3"), False),
        ]


class TestMapperContext(TestMapperBase):
    @pytest.fixture
    def dummy_driver(self):
        from ..mapper import Driver, Mapper

        class DummyDriver(Driver):
            def get_serde_identity_by_native(self, mapper: Mapper, native: typing.Any) -> str:
                return native.id if native is not None else None

            def get_native_identity_by_serde(
                self, mapper: Mapper, serde: typing.Union[ResourceRepr, ResourceIdRepr]
            ) -> typing.Any:
                return serde.id

        return DummyDriver()

    @pytest.fixture
    def dummy_serde_type_resolver(self, foo_resource_descr, bar_resource_descr, baz_resource_descr):
        from ..mapper import Mapper, SerdeTypeResolver

        class DummySerdeTypeResolver(SerdeTypeResolver):
            def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
                return descr.name

            def query_descriptor_by_type_name(self, name: str) -> ResourceDescriptor:
                if foo_resource_descr.name == name:
                    return foo_resource_descr
                elif bar_resource_descr.name == name:
                    return bar_resource_descr
                elif baz_resource_descr.name == name:
                    return baz_resource_descr
                else:
                    raise AssertionError()

            def mapper_added(self, mapper: Mapper) -> None:
                pass

        return DummySerdeTypeResolver()

    @pytest.fixture
    def dummy_endpoint_resolver(self):
        from ..mapper import EndpointResolver, Mapper, PaginatedEndpoint, ToSerdeContext

        class DummyEndpointResolver(EndpointResolver):
            def resolve_singleton_endpoint(
                self, ctx: ToSerdeContext, mapper: Mapper, native: typing.Any
            ) -> typing.Optional[URL]:
                return None

            def resolve_collection_endpoint(
                self,
                ctx: ToSerdeContext,
                mapper: Mapper,
                natives: typing.Iterable[typing.Any],
            ) -> typing.Optional[PaginatedEndpoint]:
                return None

            def resolve_to_one_relationship_endpoint(
                self,
                ctx: ToSerdeContext,
                mapper: Mapper,
                native_descr: NativeToOneRelationshipDescriptor,
                rel_descr: ResourceToOneRelationshipDescriptor,
                native: typing.Any,
            ) -> typing.Optional[URL]:
                return None

            def resolve_to_many_relationship_endpoint(
                self,
                ctx: ToSerdeContext,
                mapper: Mapper,
                native_descr: NativeToManyRelationshipDescriptor,
                rel_descr: ResourceToManyRelationshipDescriptor,
                native: typing.Any,
            ) -> typing.Optional[PaginatedEndpoint]:
                return None

        return DummyEndpointResolver()

    @pytest.fixture
    def mapper_context(self, dummy_driver, dummy_serde_type_resolver, dummy_endpoint_resolver):
        from ..mapper import MapperContext

        return MapperContext(
            driver=dummy_driver,
            serde_type_resolver=dummy_serde_type_resolver,
            endpoint_resolver=dummy_endpoint_resolver,
        )

    @pytest.fixture
    def foo_mapper(
        self, mapper_context, foo_resource_descr, foo_native_descr, identity_mapping_pair
    ):
        from ..mapper import Direction, RelationshipMapping, ToOneAttributeMapping

        return mapper_context.create_mapper(
            foo_resource_descr,
            foo_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    serde_side=foo_resource_descr.attributes[na.name],
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
                )
                for na in foo_native_descr.attributes
            ],
            relationship_mappings=[
                RelationshipMapping(foo_resource_descr.relationships[nr.name], nr)
                for nr in foo_native_descr.relationships
            ],
        )

    @pytest.fixture
    def bar_mapper(
        self,
        mapper_context,
        bar_resource_descr,
        bar_native_descr,
        foo_resource_descr,
        foo_native_descr,
        identity_mapping_pair,
    ):
        from ..mapper import Direction, RelationshipMapping, ToOneAttributeMapping

        return mapper_context.create_mapper(
            bar_resource_descr,
            bar_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    serde_side=bar_resource_descr.attributes[na.name],
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
                )
                for na in bar_native_descr.attributes
            ],
            relationship_mappings=[
                RelationshipMapping(bar_resource_descr.relationships[nr.name], nr)
                for nr in bar_native_descr.relationships
            ],
        )

    @pytest.fixture
    def baz_mapper(
        self,
        mapper_context,
        baz_resource_descr,
        baz_native_descr,
        foo_resource_descr,
        foo_native_descr,
        identity_mapping_pair,
    ):
        from ..mapper import Direction, RelationshipMapping, ToOneAttributeMapping

        return mapper_context.create_mapper(
            baz_resource_descr,
            baz_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    serde_side=baz_resource_descr.attributes[na.name],
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
                )
                for na in baz_native_descr.attributes
            ],
            relationship_mappings=[
                RelationshipMapping(baz_resource_descr.relationships[nr.name], nr)
                for nr in baz_native_descr.relationships
            ],
        )

    def test_build_serde_collection_traversing_no_constraint(
        self, mapper_context, foo_mapper, bar_mapper, baz_mapper
    ):
        from ..mapper import (
            Mapper,
            MapperContext,
            RelationshipMapping,
            RelationshipPart,
            ToSerdeContext,
        )

        bazs = [
            Baz(f=1, g="2", id="1"),
            Baz(f=3, g="4", id="2"),
        ]
        bars = [
            Bar(
                d="1",
                e=2,
                id="1",
                baz=bazs[0],
            ),
            Bar(
                d="3",
                e=4,
                id="2",
                baz=bazs[1],
            ),
        ]
        foo = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=bars[0],
            bazs=bazs,
        )
        assert all(baz.foo is foo for baz in bazs)
        assert all(baz.bar.baz is baz for baz in bazs)

        def _include_filter(
            mctx: MapperContext,
            sctx: ToSerdeContext,
            native_side: NativeRelationshipDescriptor,
            serde_side: ResourceRelationshipDescriptor,
            mapper: Mapper,
            dest_mapper: Mapper,
            native: typing.Any,
        ) -> bool:
            return True

        def _select_relationship(rel: RelationshipMapping) -> RelationshipPart:
            return RelationshipPart.ALL

        builder = mapper_context.build_serde_collection(
            Baz,
            bazs,
            select_relationship=_select_relationship,
            include_filter=_include_filter,
        )

        assert builder() == CollectionDocumentRepr(
            links=None,
            data=(
                ResourceRepr(
                    type="baz",
                    id="1",
                    links=None,
                    attributes=(
                        ("f", 1),
                        ("g", "2"),
                    ),
                    relationships=(
                        (
                            "bar",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="1",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
                            ),
                        ),
                    ),
                ),
                ResourceRepr(
                    type="baz",
                    id="2",
                    links=None,
                    attributes=(
                        ("f", 3),
                        ("g", "4"),
                    ),
                    relationships=(
                        (
                            "bar",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="2",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            included=(
                ResourceRepr(
                    type="bar",
                    id="1",
                    links=None,
                    attributes=(
                        ("d", "1"),
                        ("e", 2),
                    ),
                    relationships=[
                        (
                            "baz",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="baz",
                                    id="1",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
                            ),
                        ),
                    ],
                ),
                ResourceRepr(
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
                                links=None,
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="1",
                                ),
                            ),
                        ),
                        (
                            "bazs",
                            LinkageRepr(
                                links=None,
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
                    ],
                ),
                ResourceRepr(
                    type="bar",
                    id="2",
                    links=None,
                    attributes=(
                        ("d", "3"),
                        ("e", 4),
                    ),
                    relationships=[
                        (
                            "baz",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="baz",
                                    id="2",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=None,
                            ),
                        ),
                    ],
                ),
            ),
        )

    def test_build_serde_collection_traversing_backrefs_with_constraints(
        self, mapper_context, foo_mapper, bar_mapper, baz_mapper
    ):
        from ..mapper import (
            Mapper,
            MapperContext,
            RelationshipMapping,
            RelationshipPart,
            ToSerdeContext,
        )

        bazs = [
            Baz(f=1, g="2", id="1"),
            Baz(f=3, g="4", id="2"),
            Baz(f=5, g="6", id="3"),
        ]
        bars = [
            Bar(
                d="1",
                e=2,
                id="1",
                baz=bazs[0],
            ),
            Bar(
                d="3",
                e=4,
                id="2",
                baz=bazs[1],
            ),
            Bar(
                d="5",
                e=6,
                id="3",
                baz=bazs[2],
            ),
        ]
        foo = Foo(
            a="1",
            b=2,
            c=3,
            id="1",
            bar=bars[0],
            bazs=bazs,
        )
        assert all(baz.foo is foo for baz in bazs)
        assert all(baz.bar.baz is baz for baz in bazs)

        def _include_filter(
            mctx: MapperContext,
            sctx: ToSerdeContext,
            native_side: NativeRelationshipDescriptor,
            serde_side: ResourceRelationshipDescriptor,
            mapper: Mapper,
            dest_mapper: Mapper,
            native: typing.Any,
        ) -> bool:
            return dest_mapper is not foo_mapper

        def _select_relationship(rel: RelationshipMapping) -> RelationshipPart:
            return RelationshipPart.ALL

        builder = mapper_context.build_serde_collection(
            Bar,
            bars,
            select_relationship=_select_relationship,
            include_filter=_include_filter,
        )

        assert builder() == CollectionDocumentRepr(
            links=None,
            data=(
                ResourceRepr(
                    type="bar",
                    id="1",
                    links=None,
                    attributes=(
                        ("d", "1"),
                        ("e", 2),
                    ),
                    relationships=[
                        (
                            "baz",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="baz",
                                    id="1",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
                            ),
                        ),
                    ],
                ),
                ResourceRepr(
                    type="bar",
                    id="2",
                    links=None,
                    attributes=(
                        ("d", "3"),
                        ("e", 4),
                    ),
                    relationships=[
                        (
                            "baz",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="baz",
                                    id="2",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=None,
                            ),
                        ),
                    ],
                ),
                ResourceRepr(
                    type="bar",
                    id="3",
                    links=None,
                    attributes=(
                        ("d", "5"),
                        ("e", 6),
                    ),
                    relationships=[
                        (
                            "baz",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="baz",
                                    id="3",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=None,
                            ),
                        ),
                    ],
                ),
            ),
            included=(
                ResourceRepr(
                    type="baz",
                    id="1",
                    links=None,
                    attributes=(
                        ("f", 1),
                        ("g", "2"),
                    ),
                    relationships=(
                        (
                            "bar",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="1",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
                            ),
                        ),
                    ),
                ),
                ResourceRepr(
                    type="baz",
                    id="2",
                    links=None,
                    attributes=(
                        ("f", 3),
                        ("g", "4"),
                    ),
                    relationships=(
                        (
                            "bar",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="2",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
                            ),
                        ),
                    ),
                ),
                ResourceRepr(
                    type="baz",
                    id="3",
                    links=None,
                    attributes=(
                        ("f", 5),
                        ("g", "6"),
                    ),
                    relationships=(
                        (
                            "bar",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="bar",
                                    id="3",
                                ),
                            ),
                        ),
                        (
                            "foo",
                            LinkageRepr(
                                links=None,
                                data=ResourceIdRepr(
                                    type="foo",
                                    id="1",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )
