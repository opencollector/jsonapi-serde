import dataclasses
import typing

import pytest

from ..exceptions import ImmutableAttributeError
from ..interfaces import (
    NativeDescriptor,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipDescriptor,
)
from ..models import (
    ResourceAttributeDescriptor,
    ResourceDescriptor,
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
                ResourceToOneRelationshipDescriptor(bar_resource_descr, "bar", allow_null=True),
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
                PlainNativeToOneRelationshipDescriptor(bar_native_descr, "bar", allow_null=True),
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
                pass

            def to_many_relationship_visited(
                self,
                native_side: NativeToManyRelationshipDescriptor,
                serde_side: ResourceToManyRelationshipDescriptor,
                mapper: "Mapper",
                dest_mapper: "Mapper",
                native: typing.Any,
                dest: typing.Optional[typing.Iterable[typing.Any]],
            ) -> None:
                pass

            def native_visited(
                self,
                mapper: "Mapper",
                native: typing.Any,
            ) -> None:
                pass

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
