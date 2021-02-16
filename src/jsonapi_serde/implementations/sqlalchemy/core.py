import abc
import collections.abc
import typing
from collections import OrderedDict

import sqlalchemy as sa  # type: ignore
from sqlalchemy import orm  # type: ignore

from ...deferred import Deferred, Promise
from ...exceptions import (
    InvalidIdentifierError,
    NativeAttributeNotFoundError,
    NativeRelationshipNotFoundError,
)
from ...interfaces import (
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
)


class SQLAContext(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def query_descriptor_by_mapper(self, sa_mapper: orm.Mapper) -> "SQLADescriptor":
        ...  # pragma: nocover

    @abc.abstractmethod
    def extract_properties(
        self, sa_mapper: orm.Mapper
    ) -> typing.Iterable[orm.interfaces.MapperProperty]:
        ...  # pragma: nocover


class SQLAMutationContext(MutationContext):
    @abc.abstractmethod
    def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
        """
        Queries a native object that corresponds to the specified ``NativeDescriptor`` and identifier.

        :param descr: The descriptor for the native objects to be queried against.
        :param id: The identifier of the native object in question
        """
        ...  # pragma: nocover


def is_alien_clause(sa_mapper: orm.Mapper, expression: sa.sql.ClauseElement) -> bool:
    if not isinstance(expression, sa.Column):
        return True
    if expression.table is None:
        return True
    return expression.table not in sa_mapper.tables


Tprop = typing.TypeVar("Tprop", bound=orm.interfaces.MapperProperty)


class SQLAAttributeDescriptor(NativeAttributeDescriptor, typing.Generic[Tprop]):
    belonged_to: "SQLADescriptor"
    property: Tprop

    @property  # TODO: memoizable
    def type(self) -> typing.Optional[typing.Type]:
        if isinstance(self.property, orm.ColumnProperty):
            if not is_alien_clause(self.property.parent, self.property.expression):
                return self.property.expression.type.python_type
        elif isinstance(self.property, orm.CompositeProperty):
            return self.property.composite_class
        return None

    @property  # TODO: memoizable
    def allow_null(self) -> bool:
        if isinstance(self.property, orm.ColumnProperty):
            if not is_alien_clause(self.property.parent, self.property.expression):
                return self.property.expression.nullable
        return False

    @property  # TODO: memoizable
    def name(self) -> typing.Optional[str]:
        try:
            return self.property.key
        except AttributeError:
            return None

    def fetch_value(self, target: typing.Any) -> typing.Any:
        return self.property.class_attribute.__get__(target, None)

    def store_value(self, ctx: SQLAMutationContext, target: typing.Any, value: typing.Any) -> bool:
        if isinstance(self.property, orm.ColumnProperty):
            if is_alien_clause(self.property.parent, self.property.expression):
                # we cannot perform updates on alien columns
                return False
        prev_value = self.fetch_value(target)
        self.property.class_attribute.__set__(target, value)
        return prev_value != value

    def build_sql_expression(
        self, target_class: typing.Optional[typing.Type[typing.Any]] = None
    ) -> sa.sql.operators.Operators:
        return self.property.class_attribute.__get__(None, self.belonged_to.class_)

    def __init__(self, belonged_to: "SQLADescriptor", property: Tprop):
        self.belonged_to = belonged_to
        self.property = property


class SQLARelationshipDescriptor(NativeRelationshipDescriptor):
    belonged_to: "SQLADescriptor"
    property: orm.RelationshipProperty

    @property  # TODO: memoizable
    def destination(self) -> "SQLADescriptor":
        return self.belonged_to.sactx.query_descriptor_by_mapper(self.property.mapper)

    @property  # TODO: memoizable
    def name(self) -> typing.Optional[str]:
        try:
            return self.property.key
        except AttributeError:
            return None

    def __init__(self, belonged_to: "SQLADescriptor", property: orm.RelationshipProperty):
        self.belonged_to = belonged_to
        self.property = property


class SQLAToOneRelationshipDescriptor(
    SQLARelationshipDescriptor, NativeToOneRelationshipDescriptor
):
    def fetch_related(self, target: typing.Any) -> typing.Any:
        return self.property.class_attribute.__get__(target, None)

    def replace_related(self, target: typing.Any, new: typing.Any) -> None:
        self.property.class_attribute.__set__(target, new)


class SQLAToOneRelationshipBuilder(SQLARelationshipDescriptor, NativeToOneRelationshipBuilder):
    descr: SQLAToOneRelationshipDescriptor
    nullified: bool = False
    id: typing.Optional[typing.Sequence[typing.Any]] = None
    builder: typing.Optional["SQLABuilder"] = None

    def nullify(self):
        self.nullified = True

    def set(self, id: typing.Any):
        assert isinstance(id, collections.abc.Sequence)
        self.id = id

    def __call__(self, ctx: MutationContext) -> typing.Any:
        return self.id

    def __init__(self, descr: SQLAToOneRelationshipDescriptor):
        self.descr = descr


class Manipulation(typing.Protocol):
    added: typing.MutableSequence[typing.Tuple[typing.Any, Promise[bool]]]
    removed: typing.MutableMapping[typing.Any, Promise[bool]]


class SQLAToManyRelationshipDescriptor(
    SQLARelationshipDescriptor, NativeToManyRelationshipDescriptor
):
    def fetch_related(self, target: typing.Any) -> typing.Iterable[typing.Any]:
        return self.property.class_attribute.__get__(target, None)

    def manipulate_related(self, target: typing.Any, manip: "Manipulation"):
        col = self.fetch_related(target)
        if len(manip.removed) > 0:
            new_rels: typing.List[typing.Any] = []
            remainder = dict(manip.removed)
            for rel in col:
                id_ = self.destination.descr.get_identity(rel)
                p = remainder.pop(id_, None)
                if p is not None:
                    new_rels.append(rel)
                    p.set(True)
            for v in remainder.values():
                v.set(False)
            for added, p in manip.added:
                new_rels.append(added)
                p.set(True)
            self.replace_related(target, new_rels)
        else:
            assert hasattr(col, "append")
            for added, p in manip.added:
                col.append(added)  # type: ignore
                p.set(True)

    def replace_related(self, target: typing.Any, new: typing.Iterable[typing.Any]) -> None:
        self.property.class_attribute.__get__(target, None)[:] = new


class SQLAToManyRelationshipBuilder(NativeToManyRelationshipBuilder):
    descr: SQLAToManyRelationshipDescriptor
    ids: typing.List[typing.Sequence[typing.Any]]

    def next(self, id: typing.Any):
        assert isinstance(id, collections.abc.Sequence)
        self.ids.append(id)

    def __call__(self, ctx: MutationContext) -> typing.Iterable[typing.Any]:
        return self.ids

    def __init__(self, descr: SQLAToManyRelationshipDescriptor):
        self.descr = descr
        self.ids = []


class SQLABuilderBase:
    descr: "SQLADescriptor"
    attrs: typing.Dict[SQLAAttributeDescriptor, typing.Any]
    to_one_rels: typing.Dict[SQLAToOneRelationshipDescriptor, SQLAToOneRelationshipBuilder]
    to_many_rels: typing.Dict[SQLAToManyRelationshipDescriptor, SQLAToManyRelationshipBuilder]
    immutables: typing.Dict[SQLAAttributeDescriptor, MutatorDescriptor]

    def __setitem__(self, descr: NativeAttributeDescriptor, v: typing.Any) -> None:
        assert isinstance(descr, SQLAAttributeDescriptor)
        self.attrs[descr] = v

    def mark_immutable(
        self, descr: NativeAttributeDescriptor, mutator_descr: MutatorDescriptor
    ) -> None:
        assert isinstance(descr, SQLAAttributeDescriptor)
        self.immutables[descr] = mutator_descr

    def to_one_relationship(
        self, descr: NativeToOneRelationshipDescriptor
    ) -> NativeToOneRelationshipBuilder:
        assert isinstance(descr, SQLAToOneRelationshipDescriptor)
        builder = SQLAToOneRelationshipBuilder(descr)
        self.to_one_rels[descr] = builder
        return builder

    def to_many_relationship(
        self, descr: NativeToManyRelationshipDescriptor
    ) -> NativeToManyRelationshipBuilder:
        assert isinstance(descr, SQLAToManyRelationshipDescriptor)
        builder = SQLAToManyRelationshipBuilder(descr)
        self.to_many_rels[descr] = builder
        return builder

    def update(self, ctx: MutationContext, obj: typing.Any, update: bool):
        assert isinstance(ctx, SQLAMutationContext)
        for descr, v in self.attrs.items():
            if descr.store_value(ctx, obj, v) and update:
                mutator = self.immutables.get(descr)
                if mutator:
                    mutator.raise_immutable_attribute_error()

        for to_one_descr, to_one_builder in self.to_one_rels.items():
            id_ = to_one_builder(ctx)
            to_one_descr.replace_related(
                obj,
                (ctx.query_by_identity(to_one_descr.destination, id_) if id_ is not None else None),
            )
        for to_many_descr, to_many_builder in self.to_many_rels.items():
            to_many_descr.replace_related(
                obj,
                [
                    (
                        ctx.query_by_identity(to_many_descr.destination, id_)
                        if id_ is not None
                        else None
                    )
                    for id_ in to_many_builder(ctx)
                ],
            )

    def __init__(self, descr: "SQLADescriptor"):
        self.descr = descr
        self.attrs = {}
        self.to_one_rels = {}
        self.to_many_rels = {}
        self.immutables = {}


class SQLABuilder(SQLABuilderBase, NativeBuilder):
    def __call__(self, ctx: MutationContext) -> typing.Any:
        obj = self.descr.mapper.class_()
        self.update(ctx, obj, False)
        return obj


class SQLAToOneRelationshipManipulator(NativeToOneRelationshipManipulator):
    descr: SQLAToOneRelationshipDescriptor
    unset_id: typing.Optional[typing.Any] = None
    set_id: typing.Optional[typing.Any] = None
    promise: typing.Optional[Promise[bool]] = None

    def nullify(self) -> Deferred[bool]:
        assert self.promise is None
        self.promise = Promise[bool]()
        return self.promise

    def unset(self, id: typing.Any) -> Deferred[bool]:
        assert self.promise is None
        self.promise = Promise[bool]()
        self.unset_id = id
        return self.promise

    def set(self, id: typing.Any) -> Deferred[bool]:
        assert self.promise is None
        self.promise = Promise[bool]()
        self.set_id = id
        return self.promise

    def __init__(self, descr: SQLAToOneRelationshipDescriptor):
        self.descr = descr


class SQLAToManyRelationshipManipulator(NativeToManyRelationshipManipulator):
    descr: SQLAToManyRelationshipDescriptor
    added: typing.MutableSequence[typing.Tuple[typing.Any, Promise[bool]]]
    removed: typing.MutableMapping[typing.Any, Promise[bool]]

    def add(self, id: typing.Any) -> Deferred[bool]:
        p = Promise[bool]()
        self.added.append((id, p))
        return p

    def remove(self, id: typing.Any) -> Deferred[bool]:
        p = Promise[bool]()
        self.removed[id] = p
        return p

    def __init__(self, descr: SQLAToManyRelationshipDescriptor):
        self.descr = descr
        self.added = []
        self.removed = {}


class SQLAUpdater(SQLABuilderBase, NativeUpdater):
    target: typing.Any
    to_one_manips: typing.Dict[SQLAToOneRelationshipDescriptor, SQLAToOneRelationshipManipulator]
    to_many_manips: typing.Dict[SQLAToManyRelationshipDescriptor, SQLAToManyRelationshipManipulator]

    def to_one_relationship_manipulator(
        self, descr: NativeToOneRelationshipDescriptor
    ) -> NativeToOneRelationshipManipulator:
        assert isinstance(descr, SQLAToOneRelationshipDescriptor)
        manip = SQLAToOneRelationshipManipulator(descr)
        self.to_one_manips[descr] = manip
        return manip

    def to_many_relationship_manipulator(
        self, descr: NativeToManyRelationshipDescriptor
    ) -> NativeToManyRelationshipManipulator:
        assert isinstance(descr, SQLAToManyRelationshipDescriptor)
        manip = SQLAToManyRelationshipManipulator(descr)
        self.to_many_manips[descr] = manip
        return manip

    def __call__(self, ctx: MutationContext) -> typing.Any:
        assert isinstance(ctx, SQLAMutationContext)
        self.update(ctx, self.target, True)
        for to_one_manip in self.to_one_manips.values():
            if to_one_manip.promise is not None:
                old_obj = to_one_manip.descr.fetch_related(self.target)
                old_id = (
                    to_one_manip.descr.destination.get_identity(old_obj)
                    if old_obj is not None
                    else None
                )
                if to_one_manip.unset_id is not None:
                    if old_id == to_one_manip.unset_id:
                        to_one_manip.descr.replace_related(self.target, None)
                        to_one_manip.promise.set(True)  # type: ignore
                    else:
                        to_one_manip.promise.set(False)  # type: ignore
                else:
                    to_one_manip.descr.replace_related(
                        self.target,
                        (
                            ctx.query_by_identity(
                                to_one_manip.descr.destination, to_one_manip.set_id
                            )
                            if to_one_manip.set_id is not None
                            else None
                        ),
                    )
                    to_one_manip.promise.set(True)  # type: ignore
        for to_many_manip in self.to_many_manips.values():
            to_many_manip.descr.manipulate_related(self.target, to_many_manip)
        return self.target

    def __init__(self, descr: "SQLADescriptor", target: typing.Any):
        super().__init__(descr)
        self.target = target
        self.to_one_manips = {}
        self.to_many_manips = {}


class TableDeducible(typing.Protocol):
    local_table: sa.sql.Selectable
    selectable: sa.sql.Selectable
    persist_selectable: sa.sql.Selectable


class PropertyDeducible(typing.Protocol):
    properties: typing.Mapping[str, orm.interfaces.MapperProperty]


class SQLADescriptor(NativeDescriptor):
    sactx: SQLAContext
    mapper: orm.Mapper
    attrs_: "typing.Optional[OrderedDict[str, SQLAAttributeDescriptor]]" = None
    rels_: "typing.Optional[OrderedDict[str, SQLARelationshipDescriptor]]" = None

    @property
    def class_(self) -> type:
        return self.mapper.class_

    def new_builder(self) -> NativeBuilder:
        return SQLABuilder(self)

    def new_updater(self, target: typing.Any) -> NativeUpdater:
        return SQLAUpdater(self, target)

    def _populate_attrs_and_rels(self) -> None:
        if self.attrs_ is None:
            attrs: "OrderedDict[str, SQLAAttributeDescriptor]" = OrderedDict()
            rels: "OrderedDict[str, SQLARelationshipDescriptor]" = OrderedDict()
            pkey_cols = set(self.mapper.primary_key)
            for sa_attr in self.sactx.extract_properties(self.mapper):
                if isinstance(sa_attr, orm.ColumnProperty):
                    if (
                        isinstance(sa_attr.expression, sa.Column)
                        and sa_attr.expression in pkey_cols
                    ):
                        continue
                    attrs[sa_attr.key] = SQLAAttributeDescriptor[orm.ColumnProperty](self, sa_attr)
                elif isinstance(sa_attr, orm.CompositeProperty):
                    if all(
                        isinstance(col, sa.Column) and col in pkey_cols for col in sa_attr.columns
                    ):
                        continue
                    attrs[sa_attr.key] = SQLAAttributeDescriptor[orm.CompositeProperty](
                        self, sa_attr
                    )
                elif isinstance(sa_attr, orm.RelationshipProperty):
                    if sa_attr.uselist:
                        rels[sa_attr.key] = SQLAToManyRelationshipDescriptor(self, sa_attr)
                    else:
                        rels[sa_attr.key] = SQLAToOneRelationshipDescriptor(self, sa_attr)
            self.attrs_ = attrs
            self.rels_ = rels

    @property
    def attributes(self) -> typing.Sequence[SQLAAttributeDescriptor]:
        self._populate_attrs_and_rels()
        assert self.attrs_ is not None
        return list(self.attrs_.values())

    def get_attribute_by_name(self, name: str) -> SQLAAttributeDescriptor:
        self._populate_attrs_and_rels()
        assert self.attrs_ is not None
        try:
            return self.attrs_[name]
        except KeyError:
            raise NativeAttributeNotFoundError(self, name)

    @property
    def relationships(self) -> typing.Sequence[SQLARelationshipDescriptor]:
        self._populate_attrs_and_rels()
        assert self.rels_ is not None
        return list(self.rels_.values())

    def get_relationship_by_name(self, name: str) -> SQLARelationshipDescriptor:
        self._populate_attrs_and_rels()
        assert self.rels_ is not None
        try:
            return self.rels_[name]
        except KeyError:
            raise NativeRelationshipNotFoundError(self, name)

    def get_identity(self, target: typing.Any) -> typing.Any:
        return self.mapper.primary_key_from_instance(target)

    def build_sql_expression_from_identity(
        self,
        id: typing.Any,
        op_builder: typing.Callable[
            [typing.Optional[sa.sql.operators.Operators], sa.sql.operators.Operators, typing.Any],
            sa.sql.operators.Operators,
        ],
        table_deductible: typing.Optional[TableDeducible] = None,
    ) -> sa.sql.operators.Operators:
        assert isinstance(id, collections.abc.Sequence)
        pkey_cols = self.mapper.primary_key
        if len(pkey_cols) != len(id):
            raise InvalidIdentifierError(f'invalid identifier: "{id}"')
        table_deductible = self.mapper if table_deductible is None else table_deductible
        resulting_expr: typing.Optional[sa.sql.operators.Operators] = None
        for pkey_col, c in zip(pkey_cols, id):
            resulting_expr = op_builder(
                resulting_expr, table_deductible.selectable.columns[pkey_col.name], c
            )
        return resulting_expr

    def __init__(self, sactx: SQLAContext, mapper: orm.Mapper):
        self.sactx = sactx
        self.mapper = mapper
