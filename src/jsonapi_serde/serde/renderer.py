"""
:py:mod:`jsonapi_serde.serde.renderers` module contains a set of classes in charge of rendering internal representation of JSON-API document to JSON.

Synopsis
--------

.. code-block:: python

   import json

   from jsonapi_serde.serde.renderers import ReprRenderer

   renderer = ReprRenderer()

   internal_repr = SingletonDocumentRepr(
       links=LinksRepr(
           self_="/foos/1",
       ),
       data=ResourceRepr(
           type="foos",
           id="1",
           attributes=[
               ("a", 1),
               ("b", 2),
               ("c", 3),
           ],
           relationships=[
               (
                   "items",
                   LinkageRepr(
                       links=LinksRepr(
                           self_="/foos/1/relationships/bars/1",
                           related="/bars/1",
                       ),
                       data=[
                           ResourceIdRepr(
                               type="bars",
                               id="1",
                           ),
                           ResourceIdRepr(
                               type="bars",
                               id="2",
                           ),
                       ],
                   ),
               ),
           ],
       ),
   )

   print(json.dumps(renderer(internal_repr)))

"""

import base64
import collections.abc
import datetime
import decimal
import typing
from collections import OrderedDict

from .models import (
    AttributeValue,
    CollectionDocumentRepr,
    DocumentReprBase,
    ErrorRepr,
    LinkageRepr,
    LinksRepr,
    Repr,
    ResourceIdRepr,
    ResourceRepr,
    SingletonDocumentRepr,
    SourceRepr,
)
from .types import JSONScalar, MutableJSONObject
from .utils import JSONPointer


class TZLocalizer(typing.Protocol):
    def localize(self, dt: datetime.datetime) -> datetime.datetime:
        ...  # pragma: nocover


class ReprRendererContext:
    parent: typing.Optional["ReprRendererContext"]
    path: JSONPointer
    anchor: typing.Optional[Repr]

    def __truediv__(self, component: str) -> "ReprRendererContext":
        return self.replace(path=(self.path / component))

    def __or__(self, anchor: Repr) -> "ReprRendererContext":
        return self.replace(anchor=anchor)

    def __getitem__(self, index: int) -> "ReprRendererContext":
        return self.replace(path=(self.path[index]))

    def replace(
        self, *, anchor: typing.Optional[Repr] = None, path: typing.Optional[JSONPointer] = None
    ):
        anchor = self.anchor if anchor is None else anchor
        path = self.path if path is None else path
        return ReprRendererContext(parent=self, anchor=anchor, path=path)

    def __init__(
        self,
        parent: typing.Optional["ReprRendererContext"],
        anchor: typing.Optional[Repr] = None,
        path: typing.Optional[JSONPointer] = None,
    ):
        self.parent = parent
        self.anchor = anchor
        self.path = JSONPointer() if path is None else path


class ReprRenderer:
    _render_decimal_as_str: bool = True
    _render_embedded_links: bool = False
    _assume_naive_timezone_as: typing.Optional[datetime.tzinfo] = None

    def _dict_factory(self, items: typing.Iterator[typing.Tuple[str, typing.Any]]):
        return OrderedDict(items)

    def _render_datetime(
        self: "ReprRenderer", ctx: ReprRendererContext, repr_: AttributeValue
    ) -> JSONScalar:
        _repr = typing.cast(datetime.datetime, repr_)
        if _repr.tzinfo is None:
            if self._assume_naive_timezone_as is None:
                raise ValueError(f"{ctx.path}: naive datetime {_repr}")
            else:
                if hasattr(self._assume_naive_timezone_as, "localize"):
                    _repr = typing.cast(TZLocalizer, self._assume_naive_timezone_as).localize(_repr)
                else:
                    _repr = _repr.replace(tzinfo=self._assume_naive_timezone_as)
        return _repr.astimezone(datetime.timezone.utc).isoformat()

    def _render_date(
        self: "ReprRenderer", ctx: ReprRendererContext, repr_: AttributeValue
    ) -> JSONScalar:
        _repr = typing.cast(datetime.date, repr_)
        return _repr.isoformat()

    def _render_decimal(
        self: "ReprRenderer", ctx: ReprRendererContext, repr_: AttributeValue
    ) -> JSONScalar:
        _repr = typing.cast(decimal.Decimal, repr_)
        return str(_repr) if self._render_decimal_as_str else float(_repr)

    def _render_bytes(
        self: "ReprRenderer", ctx: ReprRendererContext, repr_: AttributeValue
    ) -> JSONScalar:
        return base64.b64encode(typing.cast(bytes, repr_)).decode("ascii")

    def _render_passthrough(
        self: "ReprRenderer", ctx: ReprRendererContext, repr_: AttributeValue
    ) -> JSONScalar:
        return typing.cast(JSONScalar, repr_)

    _supported_types: typing.ClassVar[typing.Dict[type, typing.Callable]] = {
        datetime.datetime: _render_datetime,
        datetime.date: _render_date,
        decimal.Decimal: _render_decimal,
        bytes: _render_bytes,
        str: _render_passthrough,
        int: _render_passthrough,
        float: _render_passthrough,
        bool: _render_passthrough,
        None.__class__: _render_passthrough,
    }

    def _render_scalar(self, ctx: ReprRendererContext, repr_: AttributeValue) -> JSONScalar:
        # fast pass
        r = self._supported_types.get(type(repr_))
        if r is not None:
            return r(self, ctx, repr_)

        for type_, r in self._supported_types.items():
            if isinstance(repr_, type_):
                return r(self, ctx, repr_)

        raise TypeError(f"{ctx.path}: unsupported type {repr_!r}")

    def _render_relationship(
        self, ctx: ReprRendererContext, repr_: LinkageRepr
    ) -> MutableJSONObject:
        retval: MutableJSONObject = {}
        if repr_.links is not None:
            retval["links"] = self._render_links((ctx / "links") | repr_, repr_.links)
        if isinstance(repr_.data, ResourceRepr):
            retval["data"] = self._render_resource_link((ctx / "data") | repr_, repr_.data)
        elif repr_.data is not None:
            if isinstance(repr_.data, collections.abc.Sequence):
                retval["data"] = [
                    self._render_resource_link((ctx / "data")[i] | repr_, item)
                    for i, item in enumerate(repr_.data)
                ]
            else:
                retval["data"] = self._render_resource_link((ctx / "data") | repr_, repr_.data)

        if repr_.meta:
            retval["meta"] = repr_.meta
        return retval

    def _render_resource_link(
        self, ctx: ReprRendererContext, repr_: ResourceIdRepr
    ) -> MutableJSONObject:
        retval: MutableJSONObject = {
            "type": repr_.type,
            "id": repr_.id,
        }
        if repr_.meta:
            retval["meta"] = repr_.meta
        return retval

    def _render_resource(self, ctx: ReprRendererContext, repr_: ResourceRepr) -> MutableJSONObject:
        retval: MutableJSONObject = {
            "type": repr_.type,
            "id": repr_.id,
        }
        if self._render_embedded_links and repr_.links:
            retval["links"] = self._render_links((ctx / "links") | repr_, repr_.links)
        if repr_.attributes:
            new_ctx = (ctx / "attributes") | repr_
            retval["attributes"] = self._dict_factory(
                (k, self._render_scalar(new_ctx / k, v)) for k, v in repr_.attributes.items()
            )
        if repr_.relationships:
            new_ctx = (ctx / "relationships") | repr_
            retval["relationships"] = self._dict_factory(
                (k, self._render_relationship(new_ctx / k, v))
                for k, v in repr_.relationships.items()
            )
        if repr_.meta:
            retval["meta"] = repr_.meta
        return retval

    def _render_links(self, ctx: ReprRendererContext, repr_: LinksRepr) -> MutableJSONObject:
        retval: MutableJSONObject = {}
        if repr_.self_ is not None:
            retval["self"] = repr_.self_
        if repr_.related is not None:
            retval["related"] = repr_.related
        if repr_.next is not None:
            retval["next"] = repr_.next
        if repr_.prev is not None:
            retval["prev"] = repr_.prev
        if repr_.last is not None:
            retval["last"] = repr_.last
        return retval

    def _render_source(self, ctx: ReprRendererContext, repr_: SourceRepr) -> MutableJSONObject:
        retval: MutableJSONObject = {}
        if repr_.pointer is not None:
            retval["pointer"] = repr_.pointer
        if repr_.parameter is not None:
            retval["parameter"] = repr_.parameter
        return retval

    def _render_error(self, ctx: ReprRendererContext, repr_: ErrorRepr) -> MutableJSONObject:
        retval: MutableJSONObject = {}
        if repr_.id is not None:
            retval["id"] = repr_.id
        if repr_.links is not None:
            retval["links"] = self._render_links((ctx / "links") | repr_, repr_.links)
        if repr_.status is not None:
            retval["status"] = repr_.status
        if repr_.code is not None:
            retval["code"] = repr_.code
        if repr_.title is not None:
            retval["title"] = repr_.title
        if repr_.detail is not None:
            retval["detail"] = repr_.detail
        if repr_.source is not None:
            retval["source"] = self._render_source((ctx / "source") | repr_, repr_.source)
        if repr_.meta:
            retval["meta"] = repr_.meta
        return retval

    def _populate_document_common(
        self, target: MutableJSONObject, ctx: ReprRendererContext, repr_: DocumentReprBase
    ) -> None:
        if repr_.links is not None:
            target["links"] = self._render_links((ctx / "links") | repr_, repr_.links)
        if repr_.errors:
            new_ctx = (ctx / "errors") | repr_
            target["errors"] = [
                self._render_error(new_ctx[i], e) for i, e in enumerate(repr_.errors)
            ]
        if repr_.meta:
            target["meta"] = repr_.meta

        if repr_.included:
            new_ctx = (ctx / "included") | repr_
            target["included"] = [
                self._render_resource(new_ctx[i], r) for i, r in enumerate(repr_.included)
            ]

    def _render_singleton_document(
        self, ctx: ReprRendererContext, repr_: SingletonDocumentRepr
    ) -> MutableJSONObject:
        retval: MutableJSONObject = {}
        self._populate_document_common(retval, ctx, repr_)
        if repr_.data is not None:
            retval["data"] = self._render_resource((ctx / "data") | repr_, repr_.data)
        return retval

    def _render_collection_document(
        self, ctx: ReprRendererContext, repr_: CollectionDocumentRepr
    ) -> MutableJSONObject:
        retval: MutableJSONObject = {}
        self._populate_document_common(retval, ctx, repr_)
        retval["data"] = [
            self._render_resource((ctx / "data")[i] | repr_, item)
            for i, item in enumerate(repr_.data)
        ]
        return retval

    def __call__(
        self, repr_: typing.Union[SingletonDocumentRepr, CollectionDocumentRepr]
    ) -> MutableJSONObject:
        ctx = ReprRendererContext(None)
        if isinstance(repr_, SingletonDocumentRepr):
            return self._render_singleton_document(ctx, repr_)
        elif isinstance(repr_, CollectionDocumentRepr):
            return self._render_collection_document(ctx, repr_)
        else:
            raise AssertionError("never get here")

    def __init__(
        self,
        render_decimal_as_str: bool = True,
        render_embedded_links: bool = False,
        assume_naive_timezone_as: typing.Optional[datetime.tzinfo] = None,
    ):
        self._render_decimal_as_str = render_decimal_as_str
        self._render_embedded_links = render_embedded_links
        self._assume_naive_timezone_as = assume_naive_timezone_as
