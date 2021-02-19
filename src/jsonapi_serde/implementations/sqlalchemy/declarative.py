"""
jsonapi_serde.implementations.sqlalchemy.declarative module contains a
facade implementation that is handy for use with SQLAlchemy.

Synopsis
--------

.. code-block:: python

   import sqlalchemy as sa
   from sqlalchemy import orm
   from sqlalchemy.ext.declarative import declarative_base
   from jsonapi_serde.implementations.sqlalchemy import declarative_with_defaults

   Base = declarative_base()
   decl = declarative_with_defaults()

   @decl
   class Foo(Base):
       id = sa.Column(sa.Integer(), primary_key=True, nullable=False)
       col1 = sa.Column(sa.Integer(), nullable=False)
       col2 = sa.Column(sa.String(), nullable=False)
       col3 = sa.Column(sa.DateTime(timezone=True), nullable=False)

   decl.configure()

   ...  # pragma: nocover

   session = orm.Session(...)

   serde = ResourceRepr(...)
   foo = decl.create_from_serde(session, serde)
   session.add(foo)
   session.commit()

"""
import typing

from sqlalchemy import orm  # type: ignore

from ...declarative import (
    ConverterFactory,
    InfoExtractor,
    Meta,
    build_mapping,
    handle_meta,
)
from ...defaults import (
    DefaultBasicTypeConverterImpl,
    DefaultConverterFactoryImpl,
    DefaultEndpointResolverImpl,
    DefaultSerdeTypeResolverImpl,
)
from ...mapper import (
    AttributeMapping,
    Driver,
    EndpointResolver,
    IncludeFilter,
    Mapper,
    MapperContext,
    RelationshipMapping,
    SerdeTypeResolver,
)
from ...serde.builders import (
    CollectionDocumentBuilder,
    SingletonDocumentBuilder,
    ToManyRelDocumentBuilder,
    ToOneRelDocumentBuilder,
)
from ...serde.models import ResourceIdRepr, ResourceRepr
from .core import SQLAContext, SQLADescriptor
from .defaults import (
    DefaultDriverImpl,
    DefaultInfoExtractorImpl,
    DefaultMutationContextImpl,
    DefaultStringMarshallerImpl,
    default_extract_properties,
)


class Declarative:
    """
    The facade class that sits in front of MapperContext and native implementations.
    """

    _sa_mapper_to_mapper_map: typing.Dict[orm.Mapper, Mapper]
    _instrumented_classes: typing.List[typing.Type]
    mapper_ctx: MapperContext
    info_extractor: InfoExtractor
    converter_factory: ConverterFactory
    _sqla_ctx: SQLAContext
    _extract_properties_fn: typing.Optional[
        typing.Callable[[orm.Mapper], typing.Iterable[orm.interfaces.MapperProperty]]
    ]

    class _SQLAContext(SQLAContext):
        outer: "Declarative"

        def query_descriptor_by_mapper(self, sa_mapper: orm.Mapper) -> SQLADescriptor:
            mapper = self.outer._configure_instrumented_class(sa_mapper)
            assert isinstance(mapper.native_descr, SQLADescriptor)
            return mapper.native_descr

        def extract_properties(
            self, sa_mapper: orm.Mapper
        ) -> typing.Iterable[orm.interfaces.MapperProperty]:
            if self.outer._extract_properties_fn is not None:
                return self.outer._extract_properties_fn(sa_mapper)
            else:
                return sa_mapper.attrs

        def __init__(self, outer: "Declarative"):
            self.outer = outer

    def _configure_instrumented_class(self, sa_mapper: orm.Mapper) -> Mapper:
        if sa_mapper in self._sa_mapper_to_mapper_map:
            return self._sa_mapper_to_mapper_map[sa_mapper]
        native_descr = SQLADescriptor(self._sqla_ctx, sa_mapper)
        meta: Meta
        meta_class = getattr(sa_mapper.class_, "Meta", None)
        if meta_class is not None:
            meta = handle_meta(meta_class)
        else:
            meta = Meta()
        resource_descr, attribute_mappings, relationship_mappings = build_mapping(
            meta,
            native_descr,
            self.info_extractor,
            self.mapper_ctx.query_mapper_by_native,
            self.converter_factory,
        )
        mapper = self.mapper_ctx.create_mapper(
            resource_descr=resource_descr,
            native_descr=native_descr,
            attribute_mappings=attribute_mappings,
            relationship_mappings=relationship_mappings,
            resource_filters=meta.resource_filters,
            native_builder_filters=meta.native_builder_filters,
            native_filters=meta.native_filters,
            serde_builder_filters=meta.serde_builder_filters,
        )
        self._sa_mapper_to_mapper_map[sa_mapper] = mapper
        return mapper

    def _do_configure(self):
        for c in self._instrumented_classes:
            self._configure_instrumented_class(orm.class_mapper(c))

    def create_from_serde(
        self,
        session: orm.Session,
        serde: ResourceRepr,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
    ) -> typing.Any:
        """
        Create a (native) object with the given resource representation.

        :param sqlalchemy.orm.session.Session session: SQLAlchemy session to use to fetch related objects.
        :param jsonapi_serde.serde.models.ResourceRepr serde: A ResourceRepr object from which jsonapi-serde creates the native object.
        :param callable select_relationship: An optional function that determines if the specified relationship is to be included.
        :return: An instance of SQLAlchemy-instrumented class that corresponds to the given resource representation.
        """
        mctx = DefaultMutationContextImpl(session)
        return self.mapper_ctx.create_from_serde(mctx, serde, select_attribute, select_relationship)

    Tmc = typing.TypeVar("Tmc")

    def update_with_serde(
        self,
        session: orm.Session,
        target: Tmc,
        serde: ResourceRepr,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
    ) -> Tmc:
        """
        Update the object with the given resource representation.

        :param sqlalchemy.orm.session.Session session: SQLAlchemy session to use to fetch related objects.
        :param Any target: The target object which jsonapi-serde updates with the serde representation.
        :param jsonapi_serde.serde.models.ResourceRepr serde: A ResourceRepr object with which jsonapi-serde updates the native object.
        :param callable select_attribute: An optional callable that determines if the given attribute is included.
        :param callable select_relationship: An optional callable that determines if the given relationship is included.
        :return: The updated object
        """
        mctx = DefaultMutationContextImpl(session)
        return self.mapper_ctx.update_with_serde(
            mctx, target, serde, select_attribute, select_relationship
        )

    Tmcr = typing.TypeVar("Tmcr")

    def update_to_one_rel_with_serde(
        self,
        session: orm.Session,
        target: Tmcr,
        serde_rel_name: str,
        serde: typing.Optional[ResourceIdRepr],
    ) -> Tmcr:
        mctx = DefaultMutationContextImpl(session)
        return self.mapper_ctx.update_to_one_rel_with_serde(mctx, target, serde_rel_name, serde)

    Tmcrm = typing.TypeVar("Tmcrm")

    def update_to_many_rel_with_serde(
        self,
        session: orm.Session,
        target: Tmcrm,
        serde_rel_name: str,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> Tmcrm:
        mctx = DefaultMutationContextImpl(session)
        return self.mapper_ctx.update_to_many_rel_with_serde(mctx, target, serde_rel_name, serde)

    Tmar = typing.TypeVar("Tmar")

    def add_to_one_rel_with_serde(
        self,
        session: orm.Session,
        target: Tmar,
        serde_rel_name: str,
        serde: typing.Optional[ResourceIdRepr],
    ) -> typing.Tuple[Tmar, bool]:
        mctx = DefaultMutationContextImpl(session)
        return self.mapper_ctx.add_to_one_rel_with_serde(mctx, target, serde_rel_name, serde)

    Tmrr = typing.TypeVar("Tmrr")

    def remove_to_one_rel_with_serde(
        self,
        session: orm.Session,
        target: Tmrr,
        serde_rel_name: str,
        serde: ResourceIdRepr,
    ) -> typing.Tuple[Tmrr, bool]:
        mctx = DefaultMutationContextImpl(session)
        return self.mapper_ctx.remove_to_one_rel_with_serde(mctx, target, serde_rel_name, serde)

    Tmarm = typing.TypeVar("Tmarm")

    def add_to_many_rel_with_serde(
        self,
        session: orm.Session,
        target: Tmarm,
        serde_rel_name: str,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> typing.Tuple[Tmarm, typing.Sequence[typing.Tuple[ResourceIdRepr, bool]]]:
        mctx = DefaultMutationContextImpl(session)
        return self.mapper_ctx.add_to_many_rel_with_serde(mctx, target, serde_rel_name, serde)

    Tmrrm = typing.TypeVar("Tmrrm")

    def remove_to_many_rel_with_serde(
        self,
        session: orm.Session,
        target: Tmrrm,
        serde_rel_name: str,
        serde: typing.Sequence[ResourceIdRepr],
    ) -> typing.Tuple[Tmarm, typing.Sequence[typing.Tuple[ResourceIdRepr, bool]]]:
        mctx = DefaultMutationContextImpl(session)
        return self.mapper_ctx.remove_to_many_rel_with_serde(mctx, target, serde_rel_name, serde)

    Tss = typing.TypeVar("Tss")

    def build_serde_single(
        self,
        native: Tss,
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
        traverse_relationship: typing.Optional[
            typing.Callable[["MapperContext", Mapper, RelationshipMapping, typing.Any], bool]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
    ) -> SingletonDocumentBuilder:
        """
        Render a resource from the native object.

        :param Any native: An SQLAlchemy-instrumented object to serialize.
        :param callable select_attribute: An optional callable that determines if the given attribute is included.
        :param callable select_relationship: An optional callable that determines if the given relationship is included.
        :return: A constructed builder object.
        """
        return self.mapper_ctx.build_serde_single(
            native, select_attribute, select_relationship, traverse_relationship, include_filter
        )

    Tsc = typing.TypeVar("Tsc")

    def build_serde_collection(
        self,
        native_: typing.Type[Tsc],
        natives: typing.Iterable[Tsc],
        select_attribute: typing.Optional[typing.Callable[[AttributeMapping], bool]] = None,
        select_relationship: typing.Optional[typing.Callable[[RelationshipMapping], bool]] = None,
        traverse_relationship: typing.Optional[
            typing.Callable[["MapperContext", Mapper, RelationshipMapping, typing.Any], bool]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
    ) -> CollectionDocumentBuilder:
        """
        Render a collection of resources from the iterable of native objects.

        :param Type[Any] native_: An SQLAlchemy-instrumented class.
        :param Iterable[Any] native: An iterable of SQLAlchemy-instrumented objects to serialize.
        :param callable select_attribute: An optional callable that determines if the given attribute is included.
        :param callable select_relationship: An optional callable that determines if the given relationship is included.
        :return: A constructed builder object.
        """

        return self.mapper_ctx.build_serde_collection(
            native_,
            natives,
            select_attribute,
            select_relationship,
            traverse_relationship,
            include_filter,
        )

    Trss = typing.TypeVar("Trss")

    def build_serde_rel_single(
        self,
        native: Trss,
        serde_rel_name: str,
        traverse_relationship: typing.Optional[
            typing.Callable[[MapperContext, Mapper, RelationshipMapping, typing.Any], bool]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
    ) -> ToOneRelDocumentBuilder:
        return self.mapper_ctx.build_serde_rel_single(
            native, serde_rel_name, traverse_relationship, include_filter
        )

    Trsc = typing.TypeVar("Trsc")

    def build_serde_rel_collection(
        self,
        native: Trsc,
        serde_rel_name: str,
        traverse_relationship: typing.Optional[
            typing.Callable[["MapperContext", Mapper, RelationshipMapping, typing.Any], bool]
        ] = None,
        include_filter: typing.Optional[IncludeFilter] = None,
    ) -> ToManyRelDocumentBuilder:
        return self.mapper_ctx.build_serde_rel_collection(
            native, serde_rel_name, traverse_relationship, include_filter
        )

    def configure(self, skip_configure_mappers=False) -> None:
        if not skip_configure_mappers:
            orm.configure_mappers()
        self._do_configure()

    T = typing.TypeVar("T")

    def __call__(self, instrumented_classes: typing.Type[T]) -> typing.Type[T]:
        self._instrumented_classes.append(instrumented_classes)
        return instrumented_classes

    def __init__(
        self,
        driver: Driver,
        serde_type_resolver: SerdeTypeResolver,
        endpoint_resolver: EndpointResolver,
        info_extractor: InfoExtractor,
        converter_factory: ConverterFactory,
        extract_properties_fn: typing.Optional[
            typing.Callable[[orm.Mapper], typing.Iterable[orm.interfaces.MapperProperty]]
        ] = None,
    ):
        self._sa_mapper_to_mapper_map = {}
        self._instrumented_classes = []
        self.mapper_ctx = MapperContext(
            driver=driver,
            serde_type_resolver=serde_type_resolver,
            endpoint_resolver=endpoint_resolver,
        )
        self.info_extractor = info_extractor
        self.converter_factory = converter_factory
        self._sqla_ctx = self._SQLAContext(self)
        self._extract_properties_fn = extract_properties_fn


default_marshaller = DefaultStringMarshallerImpl()


def declarative_with_defaults(
    driver: typing.Optional[Driver] = None,
    serde_type_resolver: typing.Optional[SerdeTypeResolver] = None,
    endpoint_resolver: typing.Optional[EndpointResolver] = None,
    info_extractor: typing.Optional[InfoExtractor] = None,
    converter_factory: typing.Optional[ConverterFactory] = None,
    extract_properties_fn: typing.Optional[
        typing.Callable[[orm.Mapper], typing.Iterable[orm.interfaces.MapperProperty]]
    ] = default_extract_properties,
) -> Declarative:
    return Declarative(
        driver=(driver or DefaultDriverImpl(default_marshaller)),
        serde_type_resolver=(serde_type_resolver or DefaultSerdeTypeResolverImpl()),
        endpoint_resolver=(endpoint_resolver or DefaultEndpointResolverImpl()),
        info_extractor=(info_extractor or DefaultInfoExtractorImpl()),
        converter_factory=(
            converter_factory or DefaultConverterFactoryImpl(DefaultBasicTypeConverterImpl())
        ),
        extract_properties_fn=extract_properties_fn,
    )
