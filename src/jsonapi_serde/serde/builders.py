import abc
import typing
from collections import OrderedDict

from ..utils import UNSPECIFIED, assert_not_none
from .models import (
    AttributeValue,
    CollectionDocumentRepr,
    ErrorRepr,
    LinkageRepr,
    LinksRepr,
    Repr,
    ResourceIdRepr,
    ResourceRepr,
    SingletonDocumentRepr,
    ToManyRelDocumentRepr,
    ToOneRelDocumentRepr,
)


class ReprBuilder(metaclass=abc.ABCMeta):
    parent: typing.Optional["ReprBuilder"] = None
    meta: typing.Dict[str, typing.Any]

    @abc.abstractmethod
    def __call__(self) -> typing.Optional[Repr]:
        ...  # pragma: nocover

    def __init__(self, parent: typing.Optional["ReprBuilder"] = None):
        self.parent = parent
        self.meta = {}


class NodeReprBuilder(ReprBuilder):
    links: typing.Optional[LinksRepr] = None

    def __init__(self, parent: typing.Optional["ReprBuilder"] = None):
        super().__init__(parent)
        self.links = None


class LinkageReprBuilder(NodeReprBuilder, metaclass=abc.ABCMeta):
    def __call__(self) -> LinkageRepr:
        raise NotImplementedError()


class ResourceIdReprBuilder(NodeReprBuilder):
    type: typing.Optional[str] = None
    id: typing.Optional[str] = None

    def set_type(self, type: str):
        self.type = type

    def set_id(self, id: str):
        self.id = id

    def __call__(self) -> typing.Optional[ResourceIdRepr]:
        if self.type is not None and self.id is not None:
            return ResourceIdRepr(
                type=self.type,
                id=self.id,
                meta=self.meta,
            )
        else:
            return None

    def __init__(self, parent: typing.Optional[ReprBuilder] = None):
        super().__init__(parent)


class ToManyRelReprBuilder(LinkageReprBuilder):
    data: typing.List["ResourceIdReprBuilder"]
    _done: bool = False

    def next(self) -> "ResourceIdReprBuilder":
        builder = ResourceIdReprBuilder()
        self.data.append(builder)
        return builder

    def done(self) -> None:
        self._done = True

    def __call__(self) -> LinkageRepr:
        return LinkageRepr(
            data=(tuple(assert_not_none(b()) for b in self.data) if self._done else UNSPECIFIED),
            links=self.links,
            meta=self.meta,
        )

    def __init__(self, parent: typing.Optional[ReprBuilder] = None):
        super().__init__(parent)
        self.data = []


class ToOneRelReprBuilder(LinkageReprBuilder):
    data: typing.Optional[ResourceIdReprBuilder]

    def set(self) -> "ResourceIdReprBuilder":
        self.data = builder = ResourceIdReprBuilder()
        return builder

    def __call__(self) -> LinkageRepr:
        return LinkageRepr(
            data=self.data() if self.data is not None else UNSPECIFIED,
            links=self.links,
            meta=self.meta,
        )

    def __init__(self, parent: typing.Optional[ReprBuilder] = None):
        super().__init__(parent)
        self.data = None


class ResourceReprBuilder(NodeReprBuilder):
    type: typing.Optional[str] = None
    id: typing.Optional[str] = None
    attributes: "OrderedDict[str, typing.Any]"
    relationships: "OrderedDict[str, LinkageReprBuilder]"

    def set_type(self, type: str):
        self.type = type

    def set_id(self, id: str):
        self.id = id

    def add_attribute(self, name: str, value: AttributeValue):
        self.attributes[name] = value

    def next_to_many_relationship(self, name: str) -> ToManyRelReprBuilder:
        rel = self.relationships.get(name)
        if rel is not None:
            if not isinstance(rel, ToManyRelReprBuilder):
                raise TypeError("specified relationship is not a to-many relationship")
        else:
            self.relationships[name] = rel = ToManyRelReprBuilder(self)
        return typing.cast(ToManyRelReprBuilder, rel)

    def next_to_one_relationship(self, name: str) -> ToOneRelReprBuilder:
        rel = self.relationships.get(name)
        if rel is not None:
            if not isinstance(rel, ToOneRelReprBuilder):
                raise TypeError("specified relationship is not a to-one relationship")
        else:
            self.relationships[name] = rel = ToOneRelReprBuilder(self)
        return typing.cast(ToOneRelReprBuilder, rel)

    def __call__(self) -> ResourceRepr:
        assert self.type is not None
        assert self.id is not None
        return ResourceRepr(
            type=self.type,
            id=self.id,
            links=self.links,
            meta=self.meta,
            attributes=tuple((k, v) for k, v in self.attributes.items()),
            relationships=tuple((k, v()) for k, v in self.relationships.items()),
        )

    def __init__(self, parent: typing.Optional[ReprBuilder] = None):
        super().__init__(parent)
        self.attributes = OrderedDict()
        self.relationships = OrderedDict()


class DocumentBuilder(NodeReprBuilder, metaclass=abc.ABCMeta):
    jsonapi: typing.Dict[str, typing.Any]
    errors: typing.List[ErrorRepr]
    included: typing.List[ResourceReprBuilder]

    def next_included(self) -> ResourceReprBuilder:
        b = ResourceReprBuilder(self)
        self.included.append(b)
        return b

    def __init__(self):
        super().__init__(None)
        self.jsonapi = {}
        self.errors = []
        self.included = []


class ResourceReprCollectionBuilder(typing.Protocol):
    links: typing.Optional[LinksRepr]

    def next(self) -> "ResourceReprBuilder":
        ...  # pragma: nocover

    def done(self) -> None:
        ...  # pragma: nocover


class CollectionDocumentBuilder(DocumentBuilder, ResourceReprCollectionBuilder):
    data: typing.List["ResourceReprBuilder"]
    _done: bool = False

    def next(self) -> "ResourceReprBuilder":
        builder = ResourceReprBuilder()
        self.data.append(builder)
        return builder

    def done(self) -> None:
        self._done = True

    def __call__(self) -> CollectionDocumentRepr:
        assert self._done
        return CollectionDocumentRepr(
            data=tuple(b() for b in self.data),
            errors=tuple(self.errors),
            jsonapi=self.jsonapi,
            links=self.links,
            meta=self.meta,
            included=tuple(r() for r in self.included),
        )

    def __init__(self):
        super().__init__()
        self.data = []


class SingletonDocumentBuilder(DocumentBuilder):
    data: "ResourceReprBuilder"

    def __call__(self) -> SingletonDocumentRepr:
        return SingletonDocumentRepr(
            data=self.data(),
            errors=tuple(self.errors),
            jsonapi=self.jsonapi,
            links=self.links,
            meta=self.meta,
            included=tuple(r() for r in self.included),
        )

    def __init__(self):
        super().__init__()
        self.data = ResourceReprBuilder()


class ToManyRelDocumentBuilder(DocumentBuilder):
    data: typing.List["ResourceIdReprBuilder"]
    _done: bool = False

    def next(self) -> "ResourceIdReprBuilder":
        builder = ResourceIdReprBuilder()
        self.data.append(builder)
        return builder

    def done(self) -> None:
        self._done = True

    def __call__(self) -> ToManyRelDocumentRepr:
        assert self._done
        return ToManyRelDocumentRepr(
            data=tuple(assert_not_none(b()) for b in self.data),
            errors=tuple(self.errors),
            jsonapi=self.jsonapi,
            links=self.links,
            meta=self.meta,
        )

    def __init__(self):
        super().__init__()
        self.data = []


class ToOneRelDocumentBuilder(DocumentBuilder):
    data: typing.Optional[ResourceIdReprBuilder]

    def set(self) -> "ResourceIdReprBuilder":
        self.data = builder = ResourceIdReprBuilder()
        return builder

    def __call__(self) -> ToOneRelDocumentRepr:
        assert self.data is not None
        return ToOneRelDocumentRepr(
            data=self.data(),
            errors=tuple(self.errors),
            jsonapi=self.jsonapi,
            links=self.links,
            meta=self.meta,
        )

    def __init__(self):
        super().__init__()
        self.data = None
