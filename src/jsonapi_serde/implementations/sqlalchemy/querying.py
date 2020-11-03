import operator
import typing

import sqlalchemy as sa  # type: ignore
from sqlalchemy import orm  # type: ignore

from ...interfaces import (
    MutationContext,
    NativeAttributeDescriptor,
    NativeBuilder,
    NativeToManyRelationshipBuilder,
    NativeToManyRelationshipDescriptor,
    NativeToOneRelationshipBuilder,
    NativeToOneRelationshipDescriptor,
)
from .core import (
    SQLAAttributeDescriptor,
    SQLADescriptor,
    SQLAToManyRelationshipDescriptor,
    SQLAToOneRelationshipDescriptor,
)


class ToOneQueryBuilder(NativeToOneRelationshipBuilder):
    parent: "QueryBuilder"
    descr: SQLAToOneRelationshipDescriptor
    id: typing.Optional[typing.Any] = None

    def nullify(self):
        self.id = None

    def set(self, id: typing.Any):
        self.id = id

    def __call__(self, q: orm.Query) -> typing.Tuple[orm.Query, sa.sql.operators.Operators]:
        destination_native_descr = self.descr.destination
        assert isinstance(destination_native_descr, SQLADescriptor)
        destination_class = destination_native_descr.class_
        alias = orm.aliased(destination_class)
        rel_object = self.descr.property.class_attribute.__get__(None, destination_class)
        return (
            q.join((alias, rel_object)).options(orm.contains_eager(rel_object.of_type(alias))),
            destination_native_descr.build_sql_expression_from_identity(
                self.id, identity_op, sa.inspect(alias)
            ),
        )

    def __init__(self, parent: "QueryBuilder", descr: SQLAToOneRelationshipDescriptor):
        self.parent = parent
        self.descr = descr


class ToManyQueryBuilder(NativeToManyRelationshipBuilder):
    parent: "QueryBuilder"
    descr: SQLAToManyRelationshipDescriptor
    ids: typing.List[typing.Any]

    def next(self, id: typing.Any):
        self.ids.append(id)

    def __call__(self, ctx: MutationContext) -> typing.Tuple[orm.Query, sa.sql.operators.Operators]:
        assert isinstance(ctx, orm.Query)
        destination_native_descr = self.descr.destination
        assert isinstance(destination_native_descr, SQLADescriptor)
        destination_class = destination_native_descr.class_
        alias = orm.aliased(destination_class)

        op: typing.Optional[sa.sql.operators.Operators] = None
        for id in self.ids:
            new_op = destination_native_descr.build_sql_expression_from_identity(
                id, identity_op, sa.inspect(alias)
            )
            if op is None:
                op = new_op
            else:
                op |= new_op

        rel_object = self.descr.property.class_attribute.__get__(None, destination_class)
        return (
            ctx.join((alias, rel_object)).options(orm.contains_eager(rel_object.of_type(alias))),
            op,
        )

    def __init__(self, parent: "QueryBuilder", descr: SQLAToManyRelationshipDescriptor):
        self.parent = parent
        self.descr = descr
        self.ids = []


class QueryBuilder(NativeBuilder):
    op: typing.Optional[sa.sql.operators.Operators] = None
    op_builder: typing.Callable[
        [typing.Optional[sa.sql.operators.Operators], sa.sql.operators.Operators, typing.Any],
        sa.sql.operators.Operators,
    ]
    target_class: typing.Optional[typing.Union[typing.Type[typing.Any], orm.util.AliasedClass]]
    to_one_rels: typing.Dict[NativeToOneRelationshipDescriptor, ToOneQueryBuilder]
    to_many_rels: typing.Dict[NativeToManyRelationshipDescriptor, ToManyQueryBuilder]

    def __setitem__(self, descr: NativeAttributeDescriptor, v: typing.Any) -> None:
        assert isinstance(descr, SQLAAttributeDescriptor)
        self.op = self.op_builder(self.op, descr.build_sql_expression(self.target_class), v)  # type: ignore

    def to_one_relationship(
        self, descr: NativeToOneRelationshipDescriptor
    ) -> NativeToOneRelationshipBuilder:
        assert isinstance(descr, SQLAToOneRelationshipDescriptor)
        rel = ToOneQueryBuilder(self, descr)
        self.to_one_rels[descr] = rel
        return rel

    def to_many_relationship(
        self, descr: NativeToManyRelationshipDescriptor
    ) -> NativeToManyRelationshipBuilder:
        assert isinstance(descr, SQLAToManyRelationshipDescriptor)
        rel = ToManyQueryBuilder(self, descr)
        self.to_many_rels[descr] = rel
        return rel

    def __call__(self, ctx: MutationContext) -> typing.Any:
        assert isinstance(ctx, orm.Query)
        q: orm.Query = ctx
        op = self.op
        for one_rel_builder in self.to_one_rels.values():
            q, _op = one_rel_builder(q)
            if op is None:
                op = _op
            else:
                op &= _op
        for many_rel_builder in self.to_many_rels.values():
            q, _op = many_rel_builder(q)
            if op is None:
                op = _op
            else:
                op &= _op
        return q, op

    def __init__(
        self,
        op_builder: typing.Callable[
            [typing.Optional[sa.sql.operators.Operators], sa.sql.operators.Operators, typing.Any],
            sa.sql.operators.Operators,
        ],
        target_class: typing.Optional[
            typing.Union[typing.Type[typing.Any], orm.util.AliasedClass]
        ] = None,
    ):
        self.op_builder = op_builder  # type: ignore
        self.target_class = target_class
        self.to_one_rels = {}
        self.to_many_rels = {}


MutationContext.register(orm.Query)


def build_op_builder(
    op: typing.Callable[[sa.sql.operators.Operators, typing.Any], sa.sql.operators.Operators],
    concat_op: typing.Callable[[typing.Any, typing.Any], typing.Any],
) -> typing.Callable[
    [typing.Optional[sa.sql.operators.Operators], sa.sql.operators.Operators, typing.Any],
    sa.sql.operators.Operators,
]:
    def _(
        prev_op: typing.Optional[sa.sql.operators.Operators],
        c: sa.sql.operators.Operators,
        v: typing.Any,
    ) -> sa.sql.operators.Operators:
        new_op = op(c, v)
        return new_op if prev_op is None else concat_op(prev_op, new_op)

    return _


identity_op = build_op_builder(operator.eq, operator.and_)
