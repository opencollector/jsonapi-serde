import operator
import typing
from unittest import mock

import pytest
import sqlalchemy as sa  # type: ignore
from sqlalchemy import orm  # type: ignore

from ....deferred import Deferred
from ....interfaces import (
    Endpoint,
    NativeDescriptor,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipDescriptor,
    PaginatedEndpoint,
)
from ....mapper import AttributeMapping, Mapper, RelationshipMapping
from ....mapper import ToNativeContext as _ToNativeContext
from ....mapper import ToOneAttributeMapping
from ....mapper import ToSerdeContext as _ToSerdeContext
from ....models import (
    ResourceAttributeDescriptor,
    ResourceDescriptor,
    ResourceToManyRelationshipDescriptor,
    ResourceToOneRelationshipDescriptor,
)
from ....serde.builders import ResourceReprBuilder
from ....serde.models import (
    AttributeValue,
    LinkageRepr,
    LinksRepr,
    ResourceIdRepr,
    ResourceRepr,
    Source,
)
from ....tests.test_mapper import DummyEndpoint, DummyPaginatedEndpoint


class ToSerdeContextForTesting(_ToSerdeContext):
    native_to_mapper_map: typing.Mapping[NativeDescriptor, Mapper]

    def select_attribute(self, mapping: AttributeMapping) -> bool:
        return True

    def select_relationship(self, mapping: RelationshipMapping) -> bool:
        return True

    def get_serde_identity_by_native(self, mapper: Mapper, native: typing.Any) -> str:
        sa_mapper = orm.object_mapper(native)
        return "-".join(str(v) for v in sa_mapper.primary_key_from_instance(native))

    def query_type_name_by_descriptor(self, descr: ResourceDescriptor) -> str:
        return descr.name

    def resolve_to_one_relationship_endpoint(
        self,
        mapper: "Mapper",
        native_descr: NativeToOneRelationshipDescriptor,
        rel_descr: ResourceToOneRelationshipDescriptor,
        native: typing.Any,
    ) -> Endpoint:
        parent_id = self.get_serde_identity_by_native(mapper, native)
        rel_id = self.get_serde_identity_by_native(
            self.query_mapper_by_native(native_descr.destination),
            native_descr.fetch_related(native),
        )
        return DummyEndpoint(
            self_=(
                f"/{mapper.resource_descr.name}/{parent_id}/"
                f"@{rel_descr.destination.name}/{rel_id}"
            ),
        )

    def resolve_to_many_relationship_endpoint(
        self,
        mapper: "Mapper",
        native_descr: NativeToManyRelationshipDescriptor,
        rel_descr: ResourceToManyRelationshipDescriptor,
        native: typing.Any,
    ) -> PaginatedEndpoint:
        parent_id = self.get_serde_identity_by_native(mapper, native)
        return DummyPaginatedEndpoint(
            self_=(
                f"/{mapper.resource_descr.name}/{parent_id}/"
                f"@{rel_descr.destination.name}/?page=0"
            ),
            next=(
                f"/{mapper.resource_descr.name}/{parent_id}/"
                f"@{rel_descr.destination.name}/?page=1"
            ),
        )

    def query_mapper_by_native(self, descr: NativeDescriptor) -> Mapper:
        return self.native_to_mapper_map[descr]

    def __init__(self, native_to_mapper_map: typing.Mapping[NativeDescriptor, Mapper]):
        self.native_to_mapper_map = native_to_mapper_map


class ToNativeContextForTesting(_ToNativeContext):
    serde_to_mapper_map: typing.Mapping[ResourceDescriptor, Mapper]
    type_name_to_serde_map: typing.Mapping[str, ResourceDescriptor]

    def select_relationship(self, mapping: RelationshipMapping) -> bool:
        return True

    def query_mapper_by_serde(self, descr: ResourceDescriptor) -> Mapper:
        return self.serde_to_mapper_map[descr]

    def get_native_identity_by_serde(
        self, mapper: Mapper, repr: typing.Union[ResourceRepr, ResourceIdRepr]
    ) -> typing.Any:
        if repr.id is None:
            return None
        else:
            return repr.id.split("-")

    def query_descriptor_by_type_name(self, name: str) -> ResourceDescriptor:
        return self.type_name_to_serde_map[name]

    def __init__(self, serde_to_mapper_map: typing.Mapping[ResourceDescriptor, Mapper]):
        self.serde_to_mapper_map = serde_to_mapper_map
        self.type_name_to_serde_map = {descr.name: descr for descr in serde_to_mapper_map.keys()}


def to_serde_identity_mapping(ctx: _ToSerdeContext, value: typing.Any) -> AttributeValue:
    return typing.cast(AttributeValue, value)


def to_native_identity_mapping(
    ctx: _ToNativeContext, source: Source, value: AttributeValue
) -> typing.Any:
    return value


class TestSimple:
    @pytest.fixture
    def metadata(self):
        yield sa.MetaData()

    @pytest.fixture
    def table_foo(self, metadata):
        return sa.Table(
            "foo",
            metadata,
            sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column("a", sa.String(255), nullable=False),
            sa.Column("b", sa.Integer(), nullable=False),
            sa.Column("c", sa.Integer(), nullable=False),
            sa.Column("bar_id", sa.Integer(), sa.ForeignKey("bar.id"), nullable=True),
        )

    @pytest.fixture
    def table_bar(self, metadata):
        return sa.Table(
            "bar",
            metadata,
            sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column("d", sa.String(255), nullable=False),
            sa.Column("e", sa.Integer(), nullable=False),
        )

    @pytest.fixture
    def table_baz(self, metadata, table_foo):
        return sa.Table(
            "baz",
            metadata,
            sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column("f", sa.Integer(), nullable=False),
            sa.Column("g", sa.String(255), nullable=False),
            sa.Column("foo_id", sa.Integer(), sa.ForeignKey(table_foo.c.id)),
        )

    @pytest.fixture
    def engine(self):
        yield sa.create_engine("sqlite:///")

    @pytest.fixture
    def bar_resource_descr(self):
        return ResourceDescriptor(
            name="bar",
            attributes=[
                ResourceAttributeDescriptor(
                    name="d",
                    type=str,
                    allow_null=False,
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
    def baz_resource_descr(self):
        return ResourceDescriptor(
            name="baz",
            attributes=[
                ResourceAttributeDescriptor(
                    name="f",
                    type=int,
                    allow_null=False,
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
    def foo_resource_descr(
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
                    allow_null=False,
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
    def Foo(self):
        class Foo:
            pass

        return Foo

    @pytest.fixture
    def Bar(self):
        class Bar:
            pass

        return Bar

    @pytest.fixture
    def Baz(self):
        class Baz:
            def __init__(self):
                self.f = 1
                self.g = "2"

        return Baz

    @pytest.fixture
    def foo_sa_mapper(self, table_foo, Foo, Bar, Baz):
        return orm.mapper(
            Foo,
            table_foo,
            properties={
                "bar": orm.relationship(Bar),
                "bazs": orm.relationship(Baz),
            },
        )

    @pytest.fixture
    def bar_sa_mapper(self, table_bar, Bar):
        return orm.mapper(Bar, table_bar)

    @pytest.fixture
    def baz_sa_mapper(self, table_baz, Baz):
        return orm.mapper(Baz, table_baz)

    @pytest.fixture
    def sactx(self):
        from ..core import SQLAContext as _SQLAContext
        from ..core import SQLADescriptor

        class SQLAContext(_SQLAContext):
            mapper_to_descriptor_map: typing.Dict[orm.Mapper, SQLADescriptor]

            def query_descriptor_by_mapper(self, sa_mapper: orm.Mapper) -> SQLADescriptor:
                native_descr = self.mapper_to_descriptor_map.get(sa_mapper)
                if native_descr is None:
                    self.mapper_to_descriptor_map[sa_mapper] = native_descr = SQLADescriptor(
                        self, sa_mapper
                    )
                return native_descr

            def extract_properties(
                self, sa_mapper: orm.Mapper
            ) -> typing.Iterable[orm.interfaces.MapperProperty]:
                return sa_mapper.attrs

            def __init__(self):
                self.mapper_to_descriptor_map = {}

        return SQLAContext()

    @pytest.fixture
    def foo_mapper(
        self, sactx, foo_resource_descr, foo_sa_mapper, bar_sa_mapper, baz_sa_mapper, Foo
    ):
        foo_native_descr = sactx.query_descriptor_by_mapper(foo_sa_mapper)
        return Mapper(
            foo_resource_descr,
            foo_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    ra, na, to_serde_identity_mapping, to_native_identity_mapping
                )
                for ra, na in zip(foo_resource_descr.attributes, foo_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(foo_resource_descr.relationships, foo_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def bar_mapper(self, sactx, bar_resource_descr, bar_sa_mapper, Bar):
        bar_native_descr = sactx.query_descriptor_by_mapper(bar_sa_mapper)
        return Mapper(
            bar_resource_descr,
            bar_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Bar](
                    ra, na, to_serde_identity_mapping, to_native_identity_mapping
                )
                for ra, na in zip(bar_resource_descr.attributes, bar_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(bar_resource_descr.relationships, bar_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def baz_mapper(self, sactx, baz_resource_descr, baz_sa_mapper, Baz):
        baz_native_descr = sactx.query_descriptor_by_mapper(baz_sa_mapper)
        return Mapper(
            baz_resource_descr,
            baz_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Baz](
                    ra, na, to_serde_identity_mapping, to_native_identity_mapping
                )
                for ra, na in zip(baz_resource_descr.attributes, baz_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(baz_resource_descr.relationships, baz_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def to_serde_ctx(self, foo_mapper, bar_mapper, baz_mapper):
        return ToSerdeContextForTesting(
            {
                foo_mapper.native_descr: foo_mapper,
                bar_mapper.native_descr: bar_mapper,
                baz_mapper.native_descr: baz_mapper,
            }
        )

    @pytest.fixture
    def to_native_ctx(
        self,
        foo_resource_descr,
        bar_resource_descr,
        baz_resource_descr,
        foo_mapper,
        bar_mapper,
        baz_mapper,
    ):
        return ToNativeContextForTesting(
            {
                foo_resource_descr: foo_mapper,
                bar_resource_descr: bar_mapper,
                baz_resource_descr: baz_mapper,
            }
        )

    @pytest.mark.usefixtures("bar_mapper", "baz_mapper")
    def test_build_serde(self, engine, metadata, foo_mapper, to_serde_ctx, Foo, Bar, Baz):
        session = orm.Session(bind=engine)

        metadata.create_all(bind=engine)

        f = Foo()
        f.a = "a"
        f.b = 1
        f.c = 2
        session.add(f)
        f.bar = Bar()
        f.bar.d = "3"
        f.bar.e = 4
        f.bazs = [Baz(), Baz(), Baz()]
        session.flush()

        builder = ResourceReprBuilder()
        dummy_serde_builder_context = mock.Mock()
        foo_mapper.build_serde(to_serde_ctx, dummy_serde_builder_context, builder, f)
        repr_ = builder()
        assert repr_.id == str(f.id)
        assert repr_.relationships[0][0] == "bar"
        assert repr_.relationships[0][1].data.type == "bar"
        assert repr_.relationships[0][1].data.id == str(f.bar.id)
        assert repr_.relationships[1][0] == "bazs"
        assert len(repr_.relationships[1][1].data) == 3
        assert repr_.relationships[1][1].data[0].type == "baz"
        assert repr_.relationships[1][1].data[0].id == str(f.bazs[0].id)
        assert repr_.relationships[1][1].data[1].type == "baz"
        assert repr_.relationships[1][1].data[1].id == str(f.bazs[1].id)
        assert repr_.relationships[1][1].data[2].type == "baz"
        assert repr_.relationships[1][1].data[2].id == str(f.bazs[2].id)

    @pytest.mark.usefixtures("bar_mapper", "baz_mapper")
    def test_update_with_serde(self, engine, metadata, foo_mapper, to_native_ctx, Foo, Bar, Baz):
        from ..defaults import DefaultMutationContextImpl

        session = orm.Session(bind=engine)

        metadata.create_all(bind=engine)

        foo = Foo()
        foo.a = "a"
        foo.b = 1
        foo.c = 2
        session.add(foo)
        bar = Bar()
        bar.d = "3"
        bar.e = 4
        session.add(bar)
        bazs = [Baz(), Baz(), Baz()]
        for baz in bazs:
            session.add(baz)
        session.flush()

        serde = ResourceRepr(
            type="foo",
            id="1",
            attributes=[
                ("a", "b"),
                ("b", 4),
                ("c", 5),
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

        foo_mapper.update_with_serde(to_native_ctx, DefaultMutationContextImpl(session), foo, serde)
        assert foo.id == 1
        assert foo.a == "b"
        assert foo.b == 4
        assert foo.c == 5
        assert foo.bar == bar
        assert foo.bazs == [bazs[0], bazs[1]]

    @pytest.mark.usefixtures("bar_mapper", "baz_mapper")
    def test_build_sql_expression(self, engine, metadata, foo_mapper, to_native_ctx, Foo, Bar, Baz):
        from ..querying import build_op_builder

        session = orm.Session(bind=engine)

        metadata.create_all(bind=engine)

        foo = Foo()
        foo.a = "a"
        foo.b = 1
        foo.c = 2
        session.add(foo)
        bar = Bar()
        bar.d = "3"
        bar.e = 4
        session.add(bar)
        bazs = [Baz(), Baz(), Baz()]
        for baz in bazs:
            session.add(baz)
        session.flush()

        assert (
            session.query(Foo)
            .filter(
                foo_mapper.native_descr.build_sql_expression_from_identity(
                    [foo.id], build_op_builder(operator.eq, operator.and_)
                )
            )
            .one()
            == foo
        )
        assert (
            session.query(Foo)
            .filter(foo_mapper.native_descr.attributes[0].build_sql_expression() == "a")
            .one()
            == foo
        )
        aliased_foo = orm.aliased(Foo)
        assert (
            session.query(aliased_foo)
            .filter(
                foo_mapper.native_descr.build_sql_expression_from_identity(
                    [foo.id], build_op_builder(operator.eq, operator.and_), sa.inspect(aliased_foo)
                )
            )
            .one()
            == foo
        )


class TestComposite:
    @pytest.fixture
    def metadata(self):
        yield sa.MetaData()

    @pytest.fixture
    def table_foo(self, metadata):
        return sa.Table(
            "foo",
            metadata,
            sa.Column("id1", sa.Integer(), nullable=False),
            sa.Column("id2", sa.Integer(), nullable=False),
            sa.Column("a", sa.String(255), nullable=False),
            sa.Column("b", sa.Integer(), nullable=False),
            sa.Column("c", sa.Integer(), nullable=False),
            sa.Column("bar_id1", sa.Integer(), nullable=True),
            sa.Column("bar_id2", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id1", "id2"),
            sa.ForeignKeyConstraint(("bar_id1", "bar_id2"), ("bar.id1", "bar.id2")),
        )

    @pytest.fixture
    def table_bar(self, metadata):
        return sa.Table(
            "bar",
            metadata,
            sa.Column("id1", sa.Integer(), nullable=False),
            sa.Column("id2", sa.Integer(), nullable=False),
            sa.Column("d", sa.String(255), nullable=False),
            sa.Column("e", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id1", "id2"),
        )

    @pytest.fixture
    def table_baz(self, metadata, table_foo):
        return sa.Table(
            "baz",
            metadata,
            sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column("f", sa.Integer(), nullable=False),
            sa.Column("g", sa.String(255), nullable=False),
            sa.Column("foo_id1", sa.Integer()),
            sa.Column("foo_id2", sa.Integer()),
            sa.ForeignKeyConstraint(("foo_id1", "foo_id2"), ("foo.id1", "foo.id2")),
        )

    @pytest.fixture
    def engine(self):
        yield sa.create_engine("sqlite:///")

    @pytest.fixture
    def bar_resource_descr(self):
        return ResourceDescriptor(
            name="bar",
            attributes=[
                ResourceAttributeDescriptor(
                    name="d",
                    type=str,
                    allow_null=False,
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
    def baz_resource_descr(self):
        return ResourceDescriptor(
            name="baz",
            attributes=[
                ResourceAttributeDescriptor(
                    name="f",
                    type=int,
                    allow_null=False,
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
    def foo_resource_descr(
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
                    allow_null=False,
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
    def Foo(self):
        class Foo:
            pass

        return Foo

    @pytest.fixture
    def Bar(self):
        class Bar:
            pass

        return Bar

    @pytest.fixture
    def Baz(self):
        class Baz:
            def __init__(self):
                self.f = 1
                self.g = "2"

        return Baz

    @pytest.fixture
    def foo_sa_mapper(self, table_foo, Foo, Bar, Baz):
        return orm.mapper(
            Foo,
            table_foo,
            properties={
                "bar": orm.relationship(Bar),
                "bazs": orm.relationship(Baz),
            },
        )

    @pytest.fixture
    def bar_sa_mapper(self, table_bar, Bar):
        return orm.mapper(Bar, table_bar)

    @pytest.fixture
    def baz_sa_mapper(self, table_baz, Baz):
        return orm.mapper(Baz, table_baz)

    @pytest.fixture
    def sactx(self):
        from ..core import SQLAContext as _SQLAContext
        from ..core import SQLADescriptor

        class SQLAContext(_SQLAContext):
            mapper_to_descriptor_map: typing.Dict[orm.Mapper, SQLADescriptor]

            def query_descriptor_by_mapper(self, sa_mapper: orm.Mapper) -> SQLADescriptor:
                native_descr = self.mapper_to_descriptor_map.get(sa_mapper)
                if native_descr is None:
                    self.mapper_to_descriptor_map[sa_mapper] = native_descr = SQLADescriptor(
                        self, sa_mapper
                    )
                return native_descr

            def extract_properties(
                self, sa_mapper: orm.Mapper
            ) -> typing.Iterable[orm.interfaces.MapperProperty]:
                return sa_mapper.attrs

            def __init__(self):
                self.mapper_to_descriptor_map = {}

        return SQLAContext()

    @pytest.fixture
    def foo_mapper(
        self, sactx, foo_resource_descr, foo_sa_mapper, bar_sa_mapper, baz_sa_mapper, Foo
    ):
        foo_native_descr = sactx.query_descriptor_by_mapper(foo_sa_mapper)
        return Mapper(
            foo_resource_descr,
            foo_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](
                    ra, na, to_serde_identity_mapping, to_native_identity_mapping
                )
                for ra, na in zip(foo_resource_descr.attributes, foo_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(foo_resource_descr.relationships, foo_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def bar_mapper(self, sactx, bar_resource_descr, bar_sa_mapper, Bar):
        bar_native_descr = sactx.query_descriptor_by_mapper(bar_sa_mapper)
        return Mapper(
            bar_resource_descr,
            bar_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Bar](
                    ra, na, to_serde_identity_mapping, to_native_identity_mapping
                )
                for ra, na in zip(bar_resource_descr.attributes, bar_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(bar_resource_descr.relationships, bar_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def baz_mapper(self, sactx, baz_resource_descr, baz_sa_mapper, Baz):
        baz_native_descr = sactx.query_descriptor_by_mapper(baz_sa_mapper)
        return Mapper(
            baz_resource_descr,
            baz_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Baz](
                    ra, na, to_serde_identity_mapping, to_native_identity_mapping
                )
                for ra, na in zip(baz_resource_descr.attributes, baz_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(baz_resource_descr.relationships, baz_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def to_serde_ctx(self, foo_mapper, bar_mapper, baz_mapper):
        return ToSerdeContextForTesting(
            {
                foo_mapper.native_descr: foo_mapper,
                bar_mapper.native_descr: bar_mapper,
                baz_mapper.native_descr: baz_mapper,
            }
        )

    @pytest.fixture
    def to_native_ctx(
        self,
        foo_resource_descr,
        bar_resource_descr,
        baz_resource_descr,
        foo_mapper,
        bar_mapper,
        baz_mapper,
    ):
        return ToNativeContextForTesting(
            {
                foo_resource_descr: foo_mapper,
                bar_resource_descr: bar_mapper,
                baz_resource_descr: baz_mapper,
            }
        )

    @pytest.mark.usefixtures("bar_mapper", "baz_mapper")
    def test_build_serde(self, engine, metadata, foo_mapper, to_serde_ctx, Foo, Bar, Baz):
        session = orm.Session(bind=engine)

        metadata.create_all(bind=engine)

        f = Foo()
        f.id1 = 1
        f.id2 = 2
        f.a = "a"
        f.b = 1
        f.c = 2
        session.add(f)
        f.bar = Bar()
        f.bar.id1 = 2
        f.bar.id2 = 3
        f.bar.d = "3"
        f.bar.e = 4
        f.bazs = [Baz(), Baz(), Baz()]
        session.flush()

        builder = ResourceReprBuilder()
        dummy_serde_builder_context = mock.Mock()
        foo_mapper.build_serde(to_serde_ctx, dummy_serde_builder_context, builder, f)
        repr_ = builder()
        assert repr_.id == f"{f.id1}-{f.id2}"
        assert repr_.relationships[0][0] == "bar"
        assert repr_.relationships[0][1].data.type == "bar"
        assert repr_.relationships[0][1].data.id == f"{f.bar.id1}-{f.bar.id2}"
        assert repr_.relationships[1][0] == "bazs"
        assert len(repr_.relationships[1][1].data) == 3
        assert repr_.relationships[1][1].data[0].type == "baz"
        assert repr_.relationships[1][1].data[0].id == str(f.bazs[0].id)
        assert repr_.relationships[1][1].data[1].type == "baz"
        assert repr_.relationships[1][1].data[1].id == str(f.bazs[1].id)
        assert repr_.relationships[1][1].data[2].type == "baz"
        assert repr_.relationships[1][1].data[2].id == str(f.bazs[2].id)

    @pytest.mark.usefixtures("bar_mapper", "baz_mapper")
    def test_update_with_serde(self, engine, metadata, foo_mapper, to_native_ctx, Foo, Bar, Baz):
        from ..defaults import DefaultMutationContextImpl

        session = orm.Session(bind=engine)

        metadata.create_all(bind=engine)

        foo = Foo()
        foo.id1 = 1
        foo.id2 = 1
        foo.a = "a"
        foo.b = 1
        foo.c = 2
        session.add(foo)
        bar = Bar()
        bar.id1 = 2
        bar.id2 = 3
        bar.d = "3"
        bar.e = 4
        session.add(bar)
        bazs = [Baz(), Baz(), Baz()]
        for baz in bazs:
            session.add(baz)
        session.flush()

        serde = ResourceRepr(
            type="foo",
            id="1-1",
            attributes=[
                ("a", "b"),
                ("b", 4),
                ("c", 5),
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
                            id="2-3",
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

        foo_mapper.update_with_serde(to_native_ctx, DefaultMutationContextImpl(session), foo, serde)
        assert foo.id1 == 1
        assert foo.id1 == 1
        assert foo.a == "b"
        assert foo.b == 4
        assert foo.c == 5
        assert foo.bar == bar
        assert foo.bazs == [bazs[0], bazs[1]]

    @pytest.mark.usefixtures("bar_mapper", "baz_mapper")
    def test_build_sql_expression(self, engine, metadata, foo_mapper, to_native_ctx, Foo, Bar, Baz):
        from ..querying import build_op_builder

        session = orm.Session(bind=engine)

        metadata.create_all(bind=engine)

        foo = Foo()
        foo.a = "a"
        foo.b = 1
        foo.c = 2
        foo.id1 = 1
        foo.id2 = 1
        session.add(foo)
        bar = Bar()
        bar.d = "3"
        bar.e = 4
        bar.id1 = 1
        bar.id2 = 1
        session.add(bar)
        bazs = [Baz(), Baz(), Baz()]
        for baz in bazs:
            session.add(baz)
        session.flush()

        assert (
            session.query(Foo)
            .filter(
                foo_mapper.native_descr.build_sql_expression_from_identity(
                    [foo.id1, foo.id2], build_op_builder(operator.eq, operator.and_)
                )
            )
            .one()
            == foo
        )
        assert (
            session.query(Foo)
            .filter(foo_mapper.native_descr.attributes[0].build_sql_expression() == "a")
            .one()
            == foo
        )
        aliased_foo = orm.aliased(Foo)
        assert (
            session.query(aliased_foo)
            .filter(
                foo_mapper.native_descr.build_sql_expression_from_identity(
                    [foo.id1, foo.id2],
                    build_op_builder(operator.eq, operator.and_),
                    sa.inspect(aliased_foo),
                )
            )
            .one()
            == foo
        )


class TestCircular:
    @pytest.fixture
    def metadata(self):
        yield sa.MetaData()

    @pytest.fixture
    def table_foo(self, metadata):
        return sa.Table(
            "foo",
            metadata,
            sa.Column("id", sa.Integer()),
            sa.Column("foo_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(("foo_id",), ("foo.id",)),
        )

    @pytest.fixture
    def engine(self):
        yield sa.create_engine("sqlite:///")

    @pytest.fixture
    def foo_resource_descr(self):
        resource_descr: ResourceDescriptor
        resource_descr = ResourceDescriptor(
            name="foo",
            attributes=[],
            relationships=[
                ResourceToOneRelationshipDescriptor(Deferred(lambda: resource_descr), "parent"),
                ResourceToManyRelationshipDescriptor(Deferred(lambda: resource_descr), "foos"),
            ],
        )
        return resource_descr

    @pytest.fixture
    def Foo(self):
        class Foo:
            def __init__(self, id: int):
                self.id = id

        return Foo

    @pytest.fixture
    def foo_sa_mapper(self, table_foo, Foo):
        return orm.mapper(
            Foo,
            table_foo,
            properties={
                "parent": orm.relationship(
                    Foo, foreign_keys=[table_foo.c.foo_id], remote_side=[table_foo.c.id]
                ),
                "foos": orm.relationship(Foo),
            },
        )

    @pytest.fixture
    def sactx(self):
        from ..core import SQLAContext as _SQLAContext
        from ..core import SQLADescriptor

        class SQLAContext(_SQLAContext):
            mapper_to_descriptor_map: typing.Dict[orm.Mapper, SQLADescriptor]

            def query_descriptor_by_mapper(self, sa_mapper: orm.Mapper) -> SQLADescriptor:
                native_descr = self.mapper_to_descriptor_map.get(sa_mapper)
                if native_descr is None:
                    self.mapper_to_descriptor_map[sa_mapper] = native_descr = SQLADescriptor(
                        self, sa_mapper
                    )
                return native_descr

            def extract_properties(
                self, sa_mapper: orm.Mapper
            ) -> typing.Iterable[orm.interfaces.MapperProperty]:
                return sa_mapper.attrs

            def __init__(self):
                self.mapper_to_descriptor_map = {}

        return SQLAContext()

    @pytest.fixture
    def foo_mapper(self, sactx, foo_resource_descr, foo_sa_mapper, Foo):
        foo_native_descr = sactx.query_descriptor_by_mapper(foo_sa_mapper)
        return Mapper(
            foo_resource_descr,
            foo_native_descr,
            attribute_mappings=[
                ToOneAttributeMapping[Foo](ra, na)
                for ra, na in zip(foo_resource_descr.attributes, foo_native_descr.attributes)
            ],
            relationship_mappings=[
                RelationshipMapping(rd, nd)
                for rd, nd in zip(foo_resource_descr.relationships, foo_native_descr.relationships)
            ],
        )

    @pytest.fixture
    def to_serde_ctx(self, foo_mapper):
        return ToSerdeContextForTesting(
            {
                foo_mapper.native_descr: foo_mapper,
            }
        )

    @pytest.fixture
    def to_native_ctx(
        self,
        foo_resource_descr,
        foo_mapper,
    ):
        return ToNativeContextForTesting(
            {
                foo_resource_descr: foo_mapper,
            }
        )

    def test_build_serde(self, engine, metadata, foo_mapper, to_serde_ctx, Foo):
        session = orm.Session(bind=engine)

        metadata.create_all(bind=engine)

        f = Foo(id=2)
        f.parent = Foo(id=1)
        f.foos = [Foo(id=3), Foo(id=4)]
        session.add(f)
        session.flush()

        builder = ResourceReprBuilder()
        dummy_serde_builder_context = mock.Mock()
        foo_mapper.build_serde(to_serde_ctx, dummy_serde_builder_context, builder, f)
        repr_ = builder()

        assert repr_.id == "2"
        assert repr_.relationships[0][0] == "parent"
        assert repr_.relationships[0][1].data.id == "1"
        assert repr_.relationships[1][0] == "foos"
        assert repr_.relationships[1][1].data[0].id == "3"
        assert repr_.relationships[1][1].data[1].id == "4"
