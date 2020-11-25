"""
Classes in :py:mod:`jsonapi_serde.serde.models` are abstract representation of JSON:API document elements.
"""

import dataclasses
import datetime
import decimal
import typing

from .utils import JSONPointer

Source = typing.Union[JSONPointer, str, None]


@dataclasses.dataclass
class Repr:
    """
    The base class for any model objects.
    """

    _source_: Source = None


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
        self, *, meta: typing.Optional[typing.Dict[str, typing.Any]] = None, _source_: Source = None
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
        _source_: Source = None,
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
        _source_: Source = None,
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
        _source_: Source = None,
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
AttributesRepr = typing.Sequence[typing.Tuple[str, AttributeValue]]
RelationshipsRepr = typing.Sequence[typing.Tuple[str, LinkageRepr]]


@dataclasses.dataclass(init=False)
class ResourceRepr(NodeRepr):
    """
    :py:class:`ResourceRepr` class represents a `Resource Object <https://jsonapi.org/format/#document-resource-objects>`_.
    """

    type: str  # type: ignore
    id: typing.Optional[str]  # type: ignore
    attributes: AttributesRepr = dataclasses.field(default_factory=AttributesRepr)  # type: ignore
    relationships: RelationshipsRepr = dataclasses.field(default_factory=RelationshipsRepr)  # type: ignore

    def __getitem__(self, name):
        # FIXME
        for attr_name, v in self.attributes:
            if attr_name == name:
                return v

    def __init__(
        self,
        *,
        type: str,
        id: typing.Optional[str],
        attributes: AttributesRepr,
        relationships: RelationshipsRepr = (),
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        _source_: Source = None,
    ):
        """
        :param str type: a value for ``type`` property.
        :param str id: an optional value for ``id` property.
        :param Sequence[Tuple[str, AttributeValue]] attributes: a sequence of tuples each of which represents a key-value pair of an attribute.
        :param Sequence[Tuple[str, LinksRepr]] relationships: a sequence of tuples each of which represent a key-alue pair of a relationship.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str. Any]] meta: a dictionary containing user-defined information.
        :param Union[JSONPointer, str, None] _source_: an object that describes the source of the node.
        """
        super().__init__(links=links, meta=meta, _source_=_source_)
        self.type = type
        self.id = id
        self.attributes = attributes
        self.relationships = relationships


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
        _source_: Source = None,
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
        errors: typing.Sequence[ErrorRepr] = (),
        included: typing.Sequence[ResourceRepr] = (),
        links: typing.Optional[LinksRepr] = None,
        meta: typing.Optional[typing.Dict[str, typing.Any]] = None,
        _source_: Source = None,
    ):
        """
        :param Optional[Dict[str, Any]] jsonapi:
        :param Sequence[ErrorRepr]: a sequence of :py:class:`ErrorRepr`.
        :param Sequence[ResourceRepr]: a sequence of :py:class:`ResourceRepr`.
        :param Optional[LinksRepr] links: a value for ``links`` property.
        :param Optional[Dict[str, Any]] meta: a dictionary containing user-defined information.
        :param Union[JSONPointer, str, None] source: an object that describes the source of the node.
        """
        super().__init__(links=links, meta=meta, _source_=_source_)
        self.jsonapi = jsonapi if jsonapi is not None else {}
        self.errors = errors
        self.included = included


@dataclasses.dataclass(init=False)
class SingletonDocumentRepr(DocumentReprBase):
    data: typing.Optional[ResourceRepr] = None

    def __init__(self, data: typing.Optional[ResourceRepr], **kwargs):
        super().__init__(**kwargs)
        self.data = data


@dataclasses.dataclass(init=False)
class CollectionDocumentRepr(DocumentReprBase):
    data: typing.Sequence[ResourceRepr] = ()

    def __init__(self, data: typing.Sequence[ResourceRepr], **kwargs):
        super().__init__(**kwargs)
        self.data = data
