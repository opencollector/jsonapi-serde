import sqlalchemy as sa  # type: ignore
from sqlalchemy import orm  # type: ignore
from sqlalchemy.ext.declarative import declarative_base  # type: ignore

from ....mapper import ToOneAttributeMapping
from ....serde.models import LinkageRepr, ResourceIdRepr, ResourceRepr


def test_it():
    from ..declarative import declarative_with_defaults

    decl = declarative_with_defaults()
    Base = declarative_base()

    class composite_tuple(tuple):
        def __composite_values__(self):
            return self

        def __new__(cls, *args):
            return tuple.__new__(cls, args)

    @decl
    class Foo(Base):
        __tablename__ = "foos"

        class Meta:
            attribute_mappings = [
                ("a", "a"),
                ("x", "x"),
            ]

        id = sa.Column(sa.Integer(), primary_key=True, nullable=False)
        a = sa.Column(sa.String(), nullable=True)
        x = orm.composite(
            composite_tuple,
            sa.Column("b", sa.Integer(), nullable=False),
            sa.Column("c", sa.Integer(), nullable=False),
            sa.Column("d", sa.Integer(), nullable=False),
        )
        bars = orm.relationship("Bar")

    @decl
    class Bar(Base):
        __tablename__ = "bars"
        id = sa.Column(sa.Integer(), primary_key=True, nullable=False)
        e = sa.Column(sa.Integer(), nullable=False)
        foo_id = sa.Column(sa.Integer(), sa.ForeignKey(Foo.id), nullable=True)

    decl.configure()

    mapper = decl.mapper_ctx.query_mapper_by_native_class(Foo)
    assert mapper.resource_descr.name == "foos"
    assert len(mapper.attribute_mappings) == 2
    assert isinstance(mapper.attribute_mappings[0], ToOneAttributeMapping)
    assert mapper.attribute_mappings[0].serde_side.name == "a"
    assert mapper.attribute_mappings[1].serde_side.name == "x"
    assert mapper.relationship_mappings[0].serde_side.name == "bars"

    engine = sa.create_engine("sqlite:///")
    Base.metadata.create_all(bind=engine)
    session = orm.Session(bind=engine)

    serde = ResourceRepr(
        type="foos",
        id="1",
        attributes=(
            ("a", "1"),
            ("x", composite_tuple(2, 3, 4)),
        ),
        relationships=(
            (
                "bars",
                LinkageRepr(data=()),
            ),
        ),
    )
    result = decl.create_from_serde(session=session, serde=serde)
    assert isinstance(result, Foo)
    assert result.a == "1"
    assert result.x == (2, 3, 4)

    session.add(result)
    session.flush()

    builder = decl.build_serde_single(result)
    result_repr = builder()

    assert result_repr.data == serde

    serde = ResourceRepr(
        type="bars",
        id="1",
        attributes=[
            ("e", 1),
        ],
    )
    result = decl.create_from_serde(session=session, serde=serde)
    assert isinstance(result, Bar)
    assert result.e == 1

    serde = ResourceRepr(
        type="foos",
        id="1",
        attributes=(
            ("a", None),
            ("x", composite_tuple(2, 3, 4)),
        ),
        relationships=(
            (
                "bars",
                LinkageRepr(data=()),
            ),
        ),
    )
    result2 = decl.create_from_serde(session=session, serde=serde)
    assert isinstance(result2, Foo)
    assert result2.a is None
    assert result2.x == (2, 3, 4)

    bar_1 = Bar(e=1)
    bar_2 = Bar(e=2)
    session.add(bar_1)
    session.add(bar_2)
    session.flush()
    foo = Foo()
    assert len(foo.bars) == 0
    decl.add_to_many_rel_with_serde(
        session=session,
        target=foo,
        serde_rel_name="bars",
        serde=[
            ResourceIdRepr(type="bars", id=str(bar_1.id)),
            ResourceIdRepr(type="bars", id=str(bar_2.id)),
        ],
    )
    assert len(foo.bars) == 2
    assert bar_1.foo_id == foo.id
    assert bar_2.foo_id == foo.id


def test_rel_attr():
    from ....declarative import Attr, ReadOnly
    from ..declarative import declarative_with_defaults

    decl = declarative_with_defaults()
    Base = declarative_base()

    @decl
    class Foo(Base):
        __tablename__ = "foos"

        class Meta:
            relationships_mappings = [
                ReadOnly(Attr(name="bars", allow_empty=False), "bars"),
            ]

        id = sa.Column(sa.Integer(), primary_key=True, nullable=False)
        bars = orm.relationship("Bar")

    @decl
    class Bar(Base):
        __tablename__ = "bars"
        id = sa.Column(sa.Integer(), primary_key=True, nullable=False)
        foo_id = sa.Column(sa.Integer(), sa.ForeignKey(Foo.id), nullable=False)

    decl.configure()

    mapper = decl.mapper_ctx.query_mapper_by_native_class(Foo)
    assert mapper.resource_descr.name == "foos"
    assert len(mapper.attribute_mappings) == 0
    assert mapper.relationship_mappings[0].serde_side.name == "bars"

    engine = sa.create_engine("sqlite:///")
    Base.metadata.create_all(bind=engine)
    session = orm.Session(bind=engine)

    serde = ResourceRepr(
        type="foos",
        id="1",
        attributes=(),
        relationships=(
            (
                "bars",
                LinkageRepr(data=()),
            ),
        ),
    )
    result = decl.create_from_serde(session=session, serde=serde)
    assert isinstance(result, Foo)

    session.add(result)
    session.flush()

    builder = decl.build_serde_single(result)
    result_repr = builder()

    assert result_repr.data == serde
