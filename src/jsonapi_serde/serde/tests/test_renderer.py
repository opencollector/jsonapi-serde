import datetime

import pytest


@pytest.fixture
def target_class():
    from ..renderer import ReprRenderer

    return ReprRenderer


def test_singleton(target_class):
    from ..models import (
        LinkageRepr,
        LinksRepr,
        ResourceIdRepr,
        ResourceRepr,
        SingletonDocumentRepr,
    )

    target = target_class()

    result = target(
        SingletonDocumentRepr(
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
                        "item",
                        LinkageRepr(
                            links=LinksRepr(
                                self_="/foos/1/relationships/bars/1",
                                related="/bars/1",
                            ),
                            data=ResourceIdRepr(
                                type="bars",
                                id="1",
                            ),
                        ),
                    ),
                    (
                        "items",
                        LinkageRepr(
                            links=LinksRepr(
                                self_="/foos/1/relationships/bars",
                                related="/bars",
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
        ),
    )
    assert result == {
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
                "item": {
                    "links": {
                        "self": "/foos/1/relationships/bars/1",
                        "related": "/bars/1",
                    },
                    "data": {
                        "type": "bars",
                        "id": "1",
                    },
                },
                "items": {
                    "links": {
                        "self": "/foos/1/relationships/bars",
                        "related": "/bars",
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
    }


def test_collection(target_class):
    from ..models import (
        CollectionDocumentRepr,
        LinkageRepr,
        LinksRepr,
        ResourceIdRepr,
        ResourceRepr,
    )

    target = target_class()

    result = target(
        CollectionDocumentRepr(
            links=LinksRepr(
                self_="/foos/1",
            ),
            data=[
                ResourceRepr(
                    type="foos",
                    id="1",
                    attributes=[
                        ("a", 1),
                        ("b", 2),
                        ("c", 3),
                    ],
                    relationships=[
                        (
                            "item",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_="/foos/1/relationships/bars/1",
                                    related="/bars/1",
                                ),
                                data=ResourceIdRepr(
                                    type="bars",
                                    id="1",
                                ),
                            ),
                        ),
                        (
                            "items",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_="/foos/1/relationships/bars",
                                    related="/bars",
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
                ResourceRepr(
                    type="foos",
                    id="2",
                    attributes=[
                        ("a", 3),
                        ("b", 4),
                        ("c", 5),
                    ],
                    relationships=[
                        (
                            "item",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_="/foos/1/relationships/bars/1",
                                    related="/bars/1",
                                ),
                                data=ResourceIdRepr(
                                    type="bars",
                                    id="1",
                                ),
                            ),
                        ),
                        (
                            "items",
                            LinkageRepr(
                                links=LinksRepr(
                                    self_="/foos/1/relationships/bars",
                                    related="/bars",
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
            ],
        ),
    )
    assert result == {
        "links": {
            "self": "/foos/1",
        },
        "data": [
            {
                "type": "foos",
                "id": "1",
                "attributes": {
                    "a": 1,
                    "b": 2,
                    "c": 3,
                },
                "relationships": {
                    "item": {
                        "links": {
                            "self": "/foos/1/relationships/bars/1",
                            "related": "/bars/1",
                        },
                        "data": {
                            "type": "bars",
                            "id": "1",
                        },
                    },
                    "items": {
                        "links": {
                            "self": "/foos/1/relationships/bars",
                            "related": "/bars",
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
            {
                "type": "foos",
                "id": "2",
                "attributes": {
                    "a": 3,
                    "b": 4,
                    "c": 5,
                },
                "relationships": {
                    "item": {
                        "links": {
                            "self": "/foos/1/relationships/bars/1",
                            "related": "/bars/1",
                        },
                        "data": {
                            "type": "bars",
                            "id": "1",
                        },
                    },
                    "items": {
                        "links": {
                            "self": "/foos/1/relationships/bars",
                            "related": "/bars",
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
        ],
    }


def test_to_one_rel(target_class):
    from ..models import LinksRepr, ResourceIdRepr, ToOneRelDocumentRepr

    target = target_class()

    result = target(
        ToOneRelDocumentRepr(
            links=LinksRepr(
                self_="/foos/1",
            ),
            data=ResourceIdRepr(
                type="foos",
                id="1",
            ),
        ),
    )
    assert result == {
        "links": {
            "self": "/foos/1",
        },
        "data": {
            "type": "foos",
            "id": "1",
        },
    }


def test_to_many_rel(target_class):
    from ..models import LinksRepr, ResourceIdRepr, ToManyRelDocumentRepr

    target = target_class()

    result = target(
        ToManyRelDocumentRepr(
            links=LinksRepr(
                self_="/foos/1",
            ),
            data=[
                ResourceIdRepr(
                    type="foos",
                    id="1",
                ),
                ResourceIdRepr(
                    type="foos",
                    id="2",
                ),
            ],
        ),
    )
    assert result == {
        "links": {
            "self": "/foos/1",
        },
        "data": [
            {
                "type": "foos",
                "id": "1",
            },
            {
                "type": "foos",
                "id": "2",
            },
        ],
    }


def test_naive_datetime(target_class):
    from ..models import ResourceRepr, SingletonDocumentRepr

    target = target_class()

    with pytest.raises(ValueError):
        target(
            SingletonDocumentRepr(
                data=ResourceRepr(
                    type="foos",
                    id="1",
                    attributes=[
                        ("a", datetime.datetime(1970, 1, 1, 0, 0, 0)),
                    ],
                ),
            ),
        )

    result = target(
        SingletonDocumentRepr(
            data=ResourceRepr(
                type="foos",
                id="1",
                attributes=[
                    ("a", datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)),
                ],
            ),
        )
    )

    assert result == {
        "data": {
            "type": "foos",
            "id": "1",
            "attributes": {
                "a": "1970-01-01T00:00:00+00:00",
            },
        },
    }

    target2 = target_class(assume_naive_timezone_as=datetime.timezone.utc)

    result = target2(
        SingletonDocumentRepr(
            data=ResourceRepr(
                type="foos",
                id="1",
                attributes=[
                    ("a", datetime.datetime(1970, 1, 1, 0, 0, 0)),
                ],
            ),
        )
    )

    assert result == {
        "data": {
            "type": "foos",
            "id": "1",
            "attributes": {
                "a": "1970-01-01T00:00:00+00:00",
            },
        },
    }
