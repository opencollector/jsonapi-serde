"""
Classes in :py:mod:`jsonapi_serde.serde.models` are abstract representation of JSON:API document elements.
"""

import collections.abc
import dataclasses
import datetime
import decimal
import typing
from collections import OrderedDict

from .utils import JSONPointer

Source = typing.Union[JSONPointer, str]


@dataclasses.dataclass
class Repr:
    """
    The base class for any model objects.
    """

    _source_: typing.Optional[Source] = None


@dataclasses.dataclass
class LinksRepr(Repr):
    """
    :py:class:`LinksRepr` class represents a ``links`` node of JSON:API.

    Ref.

    * `Document Links <https://jsonapi.org/format/#document-links>`_
    * `Related Resource Links <https://jsonapi.org/format/#document-resource-object-related-resource-links>`_
    """

    self_: typing.Optional[str] = None
    related: typing.Optional[str] = None
    next: typing.Optional[str] = None
    prev: typing.Optional[str] = None
    first: typing.Optional[str] = None
    last: typing.Optional[str] = None


@dataclasses.dataclass(init=False)
class MetaContainerRepr(Repr):
    """
    :py:class:`MetaContainerRepr` is an abstract base for classes containing ``meta`` node.
    """

    meta: typing.Dict[str, typing.Any] = dataclasses.field(default_factory=dict)

    def __init__(
        self,
        *,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        _source_: typing.Optional[Source] = None,
    ):
        """
        :param Optional[Dict[str. Any]] meta: a dictionary containing user-defined information.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        super().__init__(_source_=_source_)
        self.meta = meta if meta is not None else {}


@dataclasses.dataclass(init=False)
class NodeRepr(MetaContainerRepr):
    """
    :py:class:`NodeRepr` is an abstract base for classes containing ``links`` node.
    """

    links: typing.Optional[LinksRepr] = None

    def __init__(
        self,
        *,
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        _source_: typing.Optional[Source] = None,
    ):
        """
        :param Optional[LinksRepr] links: a :py:class:`LinksRepr` instance.
        :param Optional[Dict[str, Any]] meta: a dictionary containing user-defined information.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        super().__init__(meta=meta, _source_=_source_)
        self.links = links


@dataclasses.dataclass(init=False)
class ResourceIdRepr(MetaContainerRepr):
    """
    Instances of :py:class:`ResourceIdRepr` represent `Resource Identifier Objects <https://jsonapi.org/format/#document-resource-object-linkag://jsonapi.org/format/#document-resource-identifier-objects>`_
    """

    type: str  # type: ignore
    id: str  # type: ignore

    def __init__(
        self,
        *,
        type: str,
        id: str,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        _source_: typing.Optional[Source] = None,
    ):
        """
        :param str type: a value for ``type`` property.
        :param str id: a value for ``id`` property.
        :param Optional[Dict[str. Any]] meta: a dictionary containing user-defined information.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        super().__init__(meta=meta, _source_=_source_)
        self.type = type
        self.id = id


@dataclasses.dataclass(init=False)
class LinkageRepr(NodeRepr):
    """
    :py:class:`LinkageRepr` represents a `Resource Linkage <https://jsonapi.org/format/#document-resource-object-linkage>`_
    """

    data: typing.Union[None, ResourceIdRepr, typing.Sequence[ResourceIdRepr]] = None

    def __init__(
        self,
        *,
        data: typing.Union[None, ResourceIdRepr, typing.Sequence[ResourceIdRepr]],
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        _source_: typing.Optional[Source] = None,
    ):
        """
        :param Union[None, ResourceIdRepr, Sequence[ResourceIdRepr]] data: a value for ``data`` property.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str. Any]] meta: a dictionary containing user-defined information.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        super().__init__(links=links, meta=meta, _source_=_source_)
        self.data = data


AttributeScalar = typing.Union[
    datetime.datetime, datetime.date, decimal.Decimal, str, int, float, bytes, None
]
AttributeValue = typing.Union[
    typing.Sequence[AttributeScalar],
    typing.Mapping[str, AttributeScalar],
    AttributeScalar,
]


@dataclasses.dataclass(init=False)
class ResourceRepr(NodeRepr):
    """
    :py:class:`ResourceRepr` class represents a `Resource Object <https://jsonapi.org/format/#document-resource-objects>`_.
    """

    type: str  # type: ignore
    id: typing.Optional[str]  # type: ignore
    attributes: typing.Mapping[str, AttributeValue] = dataclasses.field(default_factory=OrderedDict)  # type: ignore
    relationships: typing.Mapping[str, LinkageRepr] = dataclasses.field(default_factory=OrderedDict)  # type: ignore

    def __getitem__(self, name):
        return self.attributes[name]

    def replace_attributes(
        self,
        attributes: typing.Union[
            None,
            typing.Iterable[typing.Tuple[str, AttributeValue]],
            typing.Mapping[str, AttributeValue],
        ] = None,
        **kwargs: AttributeValue,
    ):
        new_attributes: typing.MutableMapping[str, AttributeValue] = OrderedDict(
            self.attributes.items()
        )

        if isinstance(attributes, collections.abc.Mapping):
            new_attributes.update(attributes)
        elif attributes is not None:
            new_attributes.update(
                typing.cast(typing.Iterable[typing.Tuple[str, AttributeValue]], attributes)
            )
        new_attributes.update(kwargs)
        return type(self)(
            type=self.type,
            id=self.id,
            attributes=new_attributes.items(),
            relationships=self.relationships.items(),
            links=self.links,
            meta=self.meta,
            _source_=self._source_,
        )

    def __init__(
        self,
        *,
        type: str,
        id: typing.Optional[str],
        attributes: typing.Iterable[typing.Tuple[str, AttributeValue]],
        relationships: typing.Iterable[typing.Tuple[str, LinkageRepr]] = (),
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        _source_: typing.Optional[Source] = None,
    ):
        """
        :param str type: a value for ``type`` property.
        :param str id: an optional value for ``id` property.
        :param Iterable[Tuple[str, AttributeValue]] attributes: a sequence of tuples each of which represents a key-value pair of an attribute.
        :param Iterable[Tuple[str, LinkageRepr]] relationships: a sequence of tuples each of which represent a key-alue pair of a relationship.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str. Any]] meta: a dictionary containing user-defined information.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        super().__init__(links=links, meta=meta, _source_=_source_)
        self.type = type
        self.id = id
        self.attributes = OrderedDict(attributes)
        self.relationships = OrderedDict(relationships)


@dataclasses.dataclass(init=False)
class SourceRepr(Repr):
    """
    :py:class:`SourceRepr` represents a value for the ``source`` property of an `Error Object <https://jsonapi.org/format/#error-objects>`_.
    """

    pointer: typing.Optional[str] = None
    parameter: typing.Optional[str] = None

    def __init__(
        self,
        pointer: typing.Optional[str] = None,
        parameter: typing.Optional[str] = None,
        _source_: typing.Optional[Source] = None,
    ):
        super().__init__(_source_=_source_)
        self.pointer = pointer
        self.parameter = parameter


@dataclasses.dataclass
class ErrorRepr(NodeRepr):
    id: typing.Optional[str] = None
    status: typing.Optional[str] = None
    code: typing.Optional[str] = None
    title: typing.Optional[str] = None
    detail: typing.Optional[str] = None
    source: typing.Optional[SourceRepr] = None


@dataclasses.dataclass(init=False)
class DocumentReprBase(NodeRepr):
    jsonapi: typing.Dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    errors: typing.Sequence[ErrorRepr] = ()
    included: typing.Sequence[ResourceRepr] = ()

    def __init__(
        self,
        *,
        jsonapi: typing.Optional[typing.Dict[str, typing.Any]] = None,
        errors: typing.Optional[typing.Sequence[ErrorRepr]] = None,
        included: typing.Sequence[ResourceRepr] = (),
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        _source_: typing.Optional[Source] = None,
    ):
        """
        :param Optional[Dict[str, Any]] jsonapi:
        :param Optional[Sequence[ErrorRepr]]: a sequence of :py:class:`ErrorRepr`.
        :param Sequence[ResourceRepr]: a sequence of :py:class:`ResourceRepr`.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str, Any]] meta: a dictionary containing user-defined information.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        super().__init__(links=links, meta=meta, _source_=_source_)
        self.jsonapi = jsonapi if jsonapi is not None else {}
        self.errors = errors or ()
        self.included = included


class MissingType:
    def __bool__(self):
        return False

    def __init__(self):
        raise TypeError("Not directly instantiable")


Missing = object.__new__(MissingType)


@dataclasses.dataclass(init=False)
class SingletonDocumentRepr(DocumentReprBase):
    data: typing.Optional[ResourceRepr] = None

    def __init__(
        self,
        jsonapi: typing.Optional[typing.Dict[str, typing.Any]] = None,
        errors: typing.Optional[typing.Sequence[ErrorRepr]] = None,
        included: typing.Sequence[ResourceRepr] = (),
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        data: typing.Union[ResourceRepr, None, MissingType] = Missing,
        _source_: typing.Optional[Source] = None,
    ):
        """
        Either errors, meta, or data must take a non-None value.

        :param Optional[Dict[str, Any]] jsonapi:
        :param Optional[Sequence[ErrorRepr]]: a sequence of :py:class:`ErrorRepr`.
        :param Sequence[ResourceRepr]: a sequence of :py:class:`ResourceRepr`.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str, Any]] meta: a dictionary containing user-defined information.
        :param Optional[ResourceRepr] data: a ResourceRepr object.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        if data is Missing and errors is None and meta is None:
            raise ValueError("either data, errors, or meta must be specified")
        super().__init__(
            jsonapi=jsonapi,
            errors=errors,
            included=included,
            links=links,
            meta=meta,
            _source_=_source_,
        )
        self.data = (
            typing.cast(typing.Optional[ResourceRepr], data) if data is not Missing else None
        )


@dataclasses.dataclass(init=False)
class CollectionDocumentRepr(DocumentReprBase):
    data: typing.Sequence[ResourceRepr] = ()

    def __init__(
        self,
        jsonapi: typing.Optional[typing.Dict[str, typing.Any]] = None,
        errors: typing.Optional[typing.Sequence[ErrorRepr]] = None,
        included: typing.Sequence[ResourceRepr] = (),
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        data: typing.Optional[typing.Sequence[ResourceRepr]] = None,
        _source_: typing.Optional[Source] = None,
    ):
        """
        Either errors, meta, or data must take a non-None value.

        :param Optional[Dict[str, Any]] jsonapi:
        :param Optional[Sequence[ErrorRepr]]: a sequence of :py:class:`ErrorRepr`.
        :param Sequence[ResourceRepr]: a sequence of :py:class:`ResourceRepr`.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str, Any]] meta: a dictionary containing user-defined information.
        :param Optional[Sequence[ResourceRepr]] data: a ResourceRepr object.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        if data is None and errors is None and meta is None:
            raise ValueError("either data, errors, or meta must be specified")
        super().__init__(
            jsonapi=jsonapi,
            errors=errors,
            included=included,
            links=links,
            meta=meta,
            _source_=_source_,
        )
        self.data = data or ()


@dataclasses.dataclass(init=False)
class ToOneRelDocumentRepr(DocumentReprBase):
    data: typing.Optional[ResourceIdRepr] = None

    def __init__(
        self,
        jsonapi: typing.Optional[typing.Dict[str, typing.Any]] = None,
        errors: typing.Optional[typing.Sequence[ErrorRepr]] = None,
        included: typing.Sequence[ResourceRepr] = (),
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        data: typing.Union[ResourceIdRepr, None, MissingType] = Missing,
        _source_: typing.Optional[Source] = None,
    ):
        """
        Either errors, meta, or data must take a non-None value.

        :param Optional[Dict[str, Any]] jsonapi:
        :param Optional[Sequence[ErrorRepr]]: a sequence of :py:class:`ErrorRepr`.
        :param Sequence[ResourceRepr]: a sequence of :py:class:`ResourceRepr`.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str, Any]] meta: a dictionary containing user-defined information.
        :param Optional[ResourceIdRepr] data: a ResourceRepr object.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        if data is Missing and errors is None and meta is None and links is None:
            raise ValueError("either data, links, errors, or meta must be specified")
        super().__init__(
            jsonapi=jsonapi,
            errors=errors,
            included=included,
            links=links,
            meta=meta,
            _source_=_source_,
        )
        self.data = (
            typing.cast(typing.Optional[ResourceIdRepr], data) if data is not Missing else None
        )


@dataclasses.dataclass(init=False)
class ToManyRelDocumentRepr(DocumentReprBase):
    data: typing.Sequence[ResourceIdRepr] = ()

    def __init__(
        self,
        jsonapi: typing.Optional[typing.Dict[str, typing.Any]] = None,
        errors: typing.Optional[typing.Sequence[ErrorRepr]] = None,
        included: typing.Sequence[ResourceRepr] = (),
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        data: typing.Optional[typing.Sequence[ResourceIdRepr]] = None,
        _source_: typing.Optional[Source] = None,
    ):
        """
        Either errors, meta, or data must take a non-None value.

        :param Optional[Dict[str, Any]] jsonapi:
        :param Optional[Sequence[ErrorRepr]]: a sequence of :py:class:`ErrorRepr`.
        :param Sequence[ResourceRepr]: a sequence of :py:class:`ResourceRepr`.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str, Any]] meta: a dictionary containing user-defined information.
        :param Optional[Sequence[ResourceRepr]] data: a ResourceRepr object.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        if data is None and errors is None and meta is None and links is None:
            raise ValueError("either data, links, errors, or meta must be specified")
        super().__init__(
            jsonapi=jsonapi,
            errors=errors,
            included=included,
            links=links,
            meta=meta,
            _source_=_source_,
        )
        self.data = data or ()
