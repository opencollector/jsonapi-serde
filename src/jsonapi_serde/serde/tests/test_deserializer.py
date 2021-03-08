import pytest

from ..models import (
    LinkageRepr,
    LinksRepr,
    ResourceIdRepr,
    ResourceRepr,
    SingletonDocumentRepr,
)
from ..utils import JSONPointer


@pytest.fixture
def target():
    from ..deserializer import ReprDeserializer

    return ReprDeserializer


def test_basic(target):
    deser = target()

    result = deser(
        SingletonDocumentRepr,
        {
            "data": {
                "type": "foos",
                "id": "1",
                "attributes": {
                    "a": 1,
                    "b": 2,
                    "c": 3,
                },
            },
        },
    )

    assert result == SingletonDocumentRepr(
        data=ResourceRepr(
            type="foos",
            id="1",
            attributes=(
                ("a", 1),
                ("b", 2),
                ("c", 3),
            ),
            _source_=JSONPointer("/data"),
        ),
        _source_=JSONPointer("/"),
    )

    result = deser(
        SingletonDocumentRepr,
        {
            "links": {
                "self": "/foos/1",
            },
            "data": {
                "type": "foos",
                "id": "1",
                "attributes": {
                    "a": 1,
                    "b": 2,
                    "c": 3,
                },
                "relationships": {
                    "items": {
                        "links": {
                            "self": "/foos/1/relationships/bars/1",
                            "related": "/bars/1",
                        },
                        "data": [
                            {
                                "type": "bars",
                                "id": "1",
                            },
                            {
                                "type": "bars",
                                "id": "2",
                            },
                        ],
                    },
                },
            },
        },
    )

    assert result == SingletonDocumentRepr(
        links=LinksRepr(
            self_="/foos/1",
            _source_=JSONPointer("/links"),
        ),
        data=ResourceRepr(
            type="foos",
            id="1",
            attributes=(
                ("a", 1),
                ("b", 2),
                ("c", 3),
            ),
            relationships=(
                (
                    "items",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foos/1/relationships/bars/1",
                            related="/bars/1",
                            _source_=JSONPointer("/data/relationships/items/links"),
                        ),
                        data=[
                            ResourceIdRepr(
                                type="bars",
                                id="1",
                                _source_=JSONPointer("/data/relationships/items/data/0"),
                            ),
                            ResourceIdRepr(
                                type="bars",
                                id="2",
                                _source_=JSONPointer("/data/relationships/items/data/1"),
                            ),
                        ],
                        _source_=JSONPointer("/data/relationships/items"),
                    ),
                ),
            ),
            _source_=JSONPointer("/data"),
        ),
        _source_=JSONPointer("/"),
    )


def test_no_attributes(target):
    deser = target()

    result = deser(
        SingletonDocumentRepr,
        {
            "data": {
                "type": "foos",
                "id": "1",
            },
        },
    )

    assert result == SingletonDocumentRepr(
        data=ResourceRepr(
            type="foos",
            id="1",
            attributes=(),
            _source_=JSONPointer("/data"),
        ),
        _source_=JSONPointer("/"),
    )


def test_validation_error(target):
    from ..exceptions import DeserializationError

    deser = target()

    with pytest.raises(DeserializationError):
        deser(
            SingletonDocumentRepr,
            {},
        )

    with pytest.raises(DeserializationError):
        deser(
            SingletonDocumentRepr,
            {
                "links": {
                    "self": "/foos/1",
                },
                "data": {},
            },
        )

    with pytest.raises(DeserializationError):
        deser(
            SingletonDocumentRepr,
            {
                "links": {
                    "self": "/foos/1",
                },
                "data": {
                    "id": "1",
                    "attributes": {
                        "a": 1,
                        "b": 2,
                        "c": 3,
                    },
                },
            },
        )


def test_with_descriptor(target):
    from ...models import ResourceAttributeDescriptor, ResourceDescriptor

    descr = ResourceDescriptor(
        name="name",
        attributes=[
            ResourceAttributeDescriptor(int, "a"),
            ResourceAttributeDescriptor(int, "b"),
            ResourceAttributeDescriptor(int, "c", allow_null=True),
        ],
        relationships=[],
    )

    deser = target(lambda _: descr)

    result = deser(
        SingletonDocumentRepr,
        {
            "data": {
                "type": "foos",
                "id": "1",
                "attributes": {
                    "a": 1,
                    "b": 2,
                    "c": 3,
                },
            },
        },
    )

    assert result == SingletonDocumentRepr(
        data=ResourceRepr(
            type="foos",
            id="1",
            attributes=(
                ("a", 1),
                ("b", 2),
                ("c", 3),
            ),
            _source_=JSONPointer("/data"),
        ),
        _source_=JSONPointer("/"),
    )

    result = deser(
        SingletonDocumentRepr,
        {
            "data": {
                "type": "foos",
                "id": "1",
                "attributes": {
                    "a": 1,
                    "b": 2,
                    "c": None,
                },
            },
        },
    )

    assert result == SingletonDocumentRepr(
        data=ResourceRepr(
            type="foos",
            id="1",
            attributes=(
                ("a", 1),
                ("b", 2),
                ("c", None),
            ),
            _source_=JSONPointer("/data"),
        ),
        _source_=JSONPointer("/"),
    )

    result = deser(
        SingletonDocumentRepr,
        {
            "links": {
                "self": "/foos/1",
            },
            "data": {
                "type": "foos",
                "id": "1",
                "attributes": {
                    "a": 1,
                    "b": 2,
                    "c": 3,
                },
                "relationships": {
                    "items": {
                        "links": {
                            "self": "/foos/1/relationships/bars/1",
                            "related": "/bars/1",
                        },
                        "data": [
                            {
                                "type": "bars",
                                "id": "1",
                            },
                            {
                                "type": "bars",
                                "id": "2",
                            },
                        ],
                    },
                },
            },
        },
    )

    assert result == SingletonDocumentRepr(
        links=LinksRepr(
            self_="/foos/1",
            _source_=JSONPointer("/links"),
        ),
        data=ResourceRepr(
            type="foos",
            id="1",
            attributes=(
                ("a", 1),
                ("b", 2),
                ("c", 3),
            ),
            relationships=(
                (
                    "items",
                    LinkageRepr(
                        links=LinksRepr(
                            self_="/foos/1/relationships/bars/1",
                            related="/bars/1",
                            _source_=JSONPointer("/data/relationships/items/links"),
                        ),
                        data=[
                            ResourceIdRepr(
                                type="bars",
                                id="1",
                                _source_=JSONPointer("/data/relationships/items/data/0"),
                            ),
                            ResourceIdRepr(
                                type="bars",
                                id="2",
                                _source_=JSONPointer("/data/relationships/items/data/1"),
                            ),
                        ],
                        _source_=JSONPointer("/data/relationships/items"),
                    ),
                ),
            ),
            _source_=JSONPointer("/data"),
        ),
        _source_=JSONPointer("/"),
    )
