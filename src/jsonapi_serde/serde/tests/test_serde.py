import pytest


class TestSingletonDocumentBuilder:
    @pytest.fixture
    def target(self):
        from ..builders import SingletonDocumentBuilder

        return SingletonDocumentBuilder

    def test_basic(self, target):
        from ..models import LinksRepr, ResourceRepr, SingletonDocumentRepr

        b = target()
        b.links = LinksRepr(
            self_="/foos/1",
        )
        b.data.type = "foos"
        b.data.id = "1"
        b.data.add_attribute("a", 1)
        b.data.add_attribute("b", 2)
        b.data.add_attribute("c", 3)
        assert b() == SingletonDocumentRepr(
            links=LinksRepr(
                self_="/foos/1",
            ),
            data=ResourceRepr(
                type="foos",
                id="1",
                attributes=(
                    ("a", 1),
                    ("b", 2),
                    ("c", 3),
                ),
            ),
            errors=(),
            included=(),
        )
