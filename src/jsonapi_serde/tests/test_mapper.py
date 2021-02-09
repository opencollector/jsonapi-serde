import dataclasses
import typing
from unittest import mock

import pytest

from ..exceptions import ImmutableAttributeError
from ..interfaces import (
    Endpoint,
    NativeDescriptor,
    NativeToManyRelationshipDescriptor,
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
from .testing import (
    DummyEndpoint,
    DummyPaginatedEndpoint,
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


class TestMapper:
    @pytest.fixture
    def bar_resource_descr(self) -> ResourceDescriptor:
        return ResourceDescriptor(
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
            relationships=[],
        )

    @pytest.fixture
    def bar_native_descr(self) -> PlainNativeDescriptor:
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
        from ..mapper import (
            Direction,
            Mapper,
            RelationshipMapping,
            ToOneAttributeMapping,
        )

        return Mapper[Foo](
            resource_descr,
            native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    serde_side=resource_descr.attributes[na.name],
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
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
                    serde_side=ra,
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
                )
                for ra, na in zip(bar_resource_descr.attributes, bar_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(bar_resource_descr.relationships, bar_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def baz_mapper(self, baz_resource_descr, baz_native_descr, identity_mapping_pair):
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
                    serde_side=ra,
                    native_side=na,
                    to_serde_factory=identity_mapping_pair[0],
                    to_native_factory=identity_mapping_pair[1],
                    direction=Direction.BIDI,
                )
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
