import abc
import collections.abc
import datetime
import typing

import sqlalchemy as sa  # type: ignore
from sqlalchemy import orm  # type: ignore

from ...declarative import AttributeFlags, InfoExtractor, RelationshipFlags
from ...exceptions import (
    InvalidIdentifierError,
    InvalidNativeObjectStateError,
    NativeResourceNotFoundError,
)
from ...interfaces import (
    NativeAttributeDescriptor,
    NativeDescriptor,
    NativeRelationshipDescriptor,
)
from ...mapper import Driver, Mapper
from ...serde.models import AttributeScalar, ResourceIdRepr, ResourceRepr
from .core import (
    SQLAAttributeDescriptor,
    SQLADescriptor,
    SQLAMutationContext,
    SQLARelationshipDescriptor,
    SQLAToOneRelationshipDescriptor,
    is_alien_clause,
)
from .querying import identity_op


class StringMarshaller(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def to_str(self, column: sa.Column, value: typing.Any) -> str:
        ...  # pragma: nocover

    @abc.abstractmethod
    def from_str(self, column: sa.Column, value: str) -> typing.Any:
        ...  # pragma: nocover


class DefaultDriverImpl(Driver):
    marshaller: StringMarshaller

    def get_serde_identity_by_native(self, mapper: Mapper, native: typing.Any) -> str:
        sa_mapper = orm.object_mapper(native)
        pkey_values = sa_mapper.primary_key_from_instance(native)

        if all(v is None for v in pkey_values):
            raise InvalidNativeObjectStateError(
                f"native object {native!r} is not persisted yet (does not have valid primary keys)"
            )
        return " ".join(
            self.marshaller.to_str(pkey_col, v) if v is not None else "@null@"
            for pkey_col, v in zip(sa_mapper.primary_key, pkey_values)
        )

    def get_native_identity_by_serde(
        self, mapper: Mapper, serde: typing.Union[ResourceRepr, ResourceIdRepr]
    ) -> typing.Any:
        if serde.id is None:
            return None
        assert isinstance(mapper.native_descr, SQLADescriptor)
        sa_mapper = mapper.native_descr.mapper
        splitted = serde.id.split(" ")
        if len(sa_mapper.primary_key) != len(splitted):
            raise InvalidIdentifierError(f'invalid identifier: "{serde.id}"')
        return tuple(
            self.marshaller.from_str(pkey_col, c) if c != "@null@" else None
            for pkey_col, c in zip(sa_mapper.primary_key, splitted)
        )

    def __init__(self, marshaller: StringMarshaller):
        self.marshaller = marshaller


class DefaultMutationContextImpl(SQLAMutationContext):
    session: orm.Session

    def query_by_identity(self, descr: NativeDescriptor, id: typing.Any) -> typing.Any:
        assert isinstance(descr, SQLADescriptor)
        assert isinstance(id, collections.abc.Sequence)
        try:
            return (
                self.session.query(descr.class_)
                .filter(descr.build_sql_expression_from_identity(id, identity_op))
                .one()
            )
        except orm.exc.NoResultFound as e:
            raise NativeResourceNotFoundError(descr, id) from e

    def __init__(self, session: orm.Session):
        self.session = session


epoch = datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)


class DefaultStringMarshallerImpl(StringMarshaller):
    def to_str(self, column: sa.Column, value: typing.Any) -> str:
        py_type = column.type.python_type
        assert isinstance(value, py_type), f"{type(value)} != {py_type}"
        if issubclass(py_type, datetime.datetime):
            return str((value.astimezone(datetime.timezone.utc) - epoch).total_seconds())
        elif issubclass(py_type, datetime.date):
            return value.strftime("%Y-%m-%d")
        elif issubclass(py_type, datetime.time):
            return value.strftime("%H:%M:%S")
        else:
            return str(value)

    def from_str(self, column: sa.Column, value: str) -> typing.Any:
        py_type = column.type.python_type
        if issubclass(py_type, datetime.datetime):
            return datetime.datetime.utcfromtimestamp(float(value))
        elif issubclass(py_type, datetime.date):
            return datetime.datetime.strptime(value, "%Y-%m-%d").date
        elif issubclass(py_type, datetime.time):
            return datetime.datetime.strptime(value, "%H:%M:%S").time
        else:
            return py_type(value)


class DefaultInfoExtractorImpl(InfoExtractor):
    def extract_descriptor_name_for_serde(self, native_descr: NativeDescriptor) -> str:
        assert isinstance(native_descr, SQLADescriptor)
        tables = list(native_descr.mapper.tables)
        if len(tables) != 1:
            raise RuntimeError(
                f"SQLAlchemy mapper is associated to multiple tables: "
                f'{", ".join(table.name for table in tables)}'
            )
        return tables[0].name

    def extract_attribute_name_for_serde(self, native_attr_descr: NativeAttributeDescriptor) -> str:
        assert isinstance(native_attr_descr, SQLAAttributeDescriptor)
        return native_attr_descr.property.key

    def extract_attribute_type_for_serde(
        self, native_attr_descr: NativeAttributeDescriptor
    ) -> typing.Type:
        assert isinstance(native_attr_descr, SQLAAttributeDescriptor)
        if isinstance(native_attr_descr.property, orm.ColumnProperty):
            if not is_alien_clause(
                native_attr_descr.property.parent, native_attr_descr.property.expression
            ):
                return native_attr_descr.property.expression.type.python_type
        elif isinstance(native_attr_descr.property, orm.CompositeProperty):
            class_ = native_attr_descr.property.composite_class
            if issubclass(
                class_,
                typing.get_args(AttributeScalar)
                + (collections.abc.Sequence, collections.abc.Mapping),
            ):
                return class_
        raise NotImplementedError("unsupported property")

    def extract_attribute_flags_for_serde(
        self, native_attr_descr: NativeAttributeDescriptor
    ) -> AttributeFlags:
        assert isinstance(native_attr_descr, SQLAAttributeDescriptor)
        retval: AttributeFlags = AttributeFlags.NONE
        if isinstance(native_attr_descr.property, orm.ColumnProperty):
            if not is_alien_clause(
                native_attr_descr.property.parent, native_attr_descr.property.expression
            ):
                if native_attr_descr.property.expression.nullable:
                    retval |= AttributeFlags.ALLOW_NULL
                elif native_attr_descr.property.expression.default is None:
                    retval |= AttributeFlags.REQUIRED_ON_CREATION
        return retval

    def extract_relationship_name_for_serde(
        self, native_rel_descr: NativeRelationshipDescriptor
    ) -> str:
        assert isinstance(native_rel_descr, SQLARelationshipDescriptor)
        return native_rel_descr.property.key

    def extract_relationship_flags_for_serde(
        self, native_rel_descr: NativeRelationshipDescriptor
    ) -> RelationshipFlags:
        retval: RelationshipFlags = RelationshipFlags.NONE
        if isinstance(native_rel_descr, SQLAToOneRelationshipDescriptor):
            if all(local.nullable for local, _ in native_rel_descr.property.local_remote_pairs):
                retval |= RelationshipFlags.ALLOW_NULL
            if any(
                not local.nullable and local.default is None
                for local, _ in native_rel_descr.property.local_remote_pairs
            ):
                retval |= RelationshipFlags.REQUIRED_ON_CREATION
        return retval


def default_extract_properties(mapper: orm.Mapper):
    for attr in mapper.attrs:
        if isinstance(attr, orm.ColumnProperty) and isinstance(attr.expression, sa.Column):
            col = attr.expression
            if any(col.key in c.column_keys for c in col.table.foreign_key_constraints):
                continue
        yield attr
