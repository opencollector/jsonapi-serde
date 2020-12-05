import dataclasses
import typing

import pytest

from ..mapper import Direction
from ..models import ResourceAttributeDescriptor
from .testing import (
    PlainInfoExtractor,
    PlainNativeAttributeDescriptor,
    PlainNativeDescriptor,
    PlainNativeToManyRelationshipDescriptor,
    PlainNativeToOneRelationshipDescriptor,
)


@dataclasses.dataclass
class Foo:
    a: str
    b: int
    c: int
    bar: typing.Optional["Bar"] = None
    bazs: typing.Optional[typing.Sequence["Baz"]] = None
    id: typing.Optional[int] = None


@dataclasses.dataclass
class Bar:
    d: typing.Optional[str]
    e: int
    id: typing.Optional[int] = None


@dataclasses.dataclass
class Baz:
    f: int
    g: str
    id: typing.Optional[int] = None


class TestDeclarative:
    @pytest.fixture
    def foo_native_descr(self, bar_native_descr, baz_native_descr):
        return PlainNativeDescriptor(
            class_=Foo,
            attributes=[
                PlainNativeAttributeDescriptor("a", str, False),
                PlainNativeAttributeDescriptor("b", int, True),
                PlainNativeAttributeDescriptor("c", int, False),
            ],
            relationships=[
                PlainNativeToOneRelationshipDescriptor(bar_native_descr, "bar"),
                PlainNativeToManyRelationshipDescriptor(baz_native_descr, "bazs"),
            ],
        )

    @pytest.fixture
    def bar_native_descr(self) -> PlainNativeDescriptor:
        return PlainNativeDescriptor(
            Bar,
            attributes=[
                PlainNativeAttributeDescriptor("d", str, True),
                PlainNativeAttributeDescriptor("e", int, False),
            ],
        )

    @pytest.fixture
    def baz_native_descr(self):
        return PlainNativeDescriptor(
            Baz,
            attributes=[
                PlainNativeAttributeDescriptor("f", int, True),
                PlainNativeAttributeDescriptor("g", str, False),
            ],
        )

    def test_build_mapping_auto(self, foo_native_descr):
        from ..declarative import build_mapping, handle_meta
        from ..defaults import (
            DefaultBasicTypeConverterImpl,
            DefaultConverterFactoryImpl,
        )

        class Meta:
            pass

        foo_descr, attr_mappings, rel_mappings = build_mapping(
            meta=handle_meta(Meta),
            native_descr=foo_native_descr,
            info_extractor=PlainInfoExtractor(),
            query_mapper_by_native=lambda native_descr: None,
            converter_factory=DefaultConverterFactoryImpl(DefaultBasicTypeConverterImpl()),
        )

        assert len(foo_descr.attributes) == 3
        assert foo_descr.attributes["c"].type is int

    def test_build_mapping_proto(self, foo_native_descr):
        from ..declarative import ReadOnly, WriteOnly, build_mapping, handle_meta
        from ..defaults import (
            DefaultBasicTypeConverterImpl,
            DefaultConverterFactoryImpl,
        )

        class Meta:
            attribute_mappings = [
                ("a", "a"),
                ReadOnly("b", "b"),
                WriteOnly("c", "c"),
            ]

        foo_descr, attr_mappings, rel_mappings = build_mapping(
            meta=handle_meta(Meta),
            native_descr=foo_native_descr,
            info_extractor=PlainInfoExtractor(),
            query_mapper_by_native=lambda native_descr: None,
            converter_factory=DefaultConverterFactoryImpl(DefaultBasicTypeConverterImpl()),
        )

        assert len(foo_descr.attributes) == 3
        assert len(attr_mappings) == 3
        assert foo_descr.attributes["a"].type is str
        assert attr_mappings[0].direction is Direction.BIDI
        assert foo_descr.attributes["b"].type is int
        assert attr_mappings[1].direction is Direction.TO_SERDE_ONLY
        assert foo_descr.attributes["c"].type is int
        assert attr_mappings[2].direction is Direction.TO_NATIVE_ONLY

    def test_build_mapping_serde_side_decl(self, foo_native_descr):
        from ..declarative import InvalidDeclarationError, build_mapping, handle_meta
        from ..defaults import (
            DefaultBasicTypeConverterImpl,
            DefaultConverterFactoryImpl,
        )

        class Meta:
            serde_side = {
                "attributes": {
                    "c": ResourceAttributeDescriptor(
                        type=int,
                        read_only=True,
                    ),
                },
            }

        with pytest.raises(InvalidDeclarationError):
            foo_descr, attr_mappings, rel_mappings = build_mapping(
                meta=handle_meta(Meta),
                native_descr=foo_native_descr,
                info_extractor=PlainInfoExtractor(),
                query_mapper_by_native=lambda native_descr: None,
                converter_factory=DefaultConverterFactoryImpl(DefaultBasicTypeConverterImpl()),
            )

    def test_build_mapping_serde_side_decl_ok(self, foo_native_descr):
        from ..declarative import build_mapping, handle_meta
        from ..defaults import (
            DefaultBasicTypeConverterImpl,
            DefaultConverterFactoryImpl,
        )

        class Meta:
            serde_side = {
                "attributes": {
                    "a": ResourceAttributeDescriptor(
                        type=str,
                        read_only=True,
                    ),
                    "b": ResourceAttributeDescriptor(
                        type=int,
                        read_only=True,
                    ),
                    "c": ResourceAttributeDescriptor(
                        type=int,
                        read_only=True,
                    ),
                },
            }

        foo_descr, attr_mappings, rel_mappings = build_mapping(
            meta=handle_meta(Meta),
            native_descr=foo_native_descr,
            info_extractor=PlainInfoExtractor(),
            query_mapper_by_native=lambda native_descr: None,
            converter_factory=DefaultConverterFactoryImpl(DefaultBasicTypeConverterImpl()),
        )

        assert len(foo_descr.attributes) == 3
        assert foo_descr.attributes["c"].type is int
        assert [am.direction for am in attr_mappings] == [Direction.TO_SERDE_ONLY] * 3
