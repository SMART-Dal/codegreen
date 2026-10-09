"""Typed Python call resolution: module-qualified keys, the confidence
cascade (imports 0.95, same module 0.90, self/cls/super on the class
hierarchy 0.95, unique name 0.75, else 0.5) and no edge into external code."""
import pytest

from codegreen.analysis.cfg.callgraph import build_call_graph, transitive_callers

FILES = {
    "pkg/__init__.py": "",
    "pkg/util.py": "def lowbits(x):\n    return x & 0xFFFF\n\ndef helper():\n    return 1\n",
    "pkg/other/util.py": "def lowbits(x):\n    return 0\n",
    "pkg/base.py": ("class Container:\n    def add(self, x):\n        return self\n\n"
                    "    def size(self):\n        return 0\n"),
    "pkg/bitmap.py": (
        "import os\n"
        "import pkg.util as u\n"
        "from .base import Container\n"
        "from .util import helper\n\n"
        "class Run(Container):\n"
        "    def __init__(self):\n        self.n = 0\n\n"
        "    def add(self, x):\n        super().add(x)\n        return self\n\n"
        "class Bitmap:\n"
        "    def checked_add(self, x, c):\n"
        "        lb = u.lowbits(x)\n"
        "        self.grow()\n"
        "        helper()\n"
        "        local()\n"
        "        r = Run()\n"
        "        os.path.join('a', 'b')\n"
        "        return c.size()\n\n"
        "    def grow(self):\n        return 1\n\n"
        "def local():\n    return 2\n"),
}


@pytest.fixture(scope="module")
def cg():
    return build_call_graph(FILES)


def test_module_qualified_keys_do_not_collide(cg):
    assert {"pkg.util.lowbits", "pkg.other.util.lowbits", "pkg.bitmap.Bitmap.checked_add"} <= set(cg.methods)


def test_cascade_confidences(cg):
    t = cg.methods["pkg.bitmap.Bitmap.checked_add"].typed_callees
    assert t["pkg.util.lowbits"] == 0.95 and "pkg.other.util.lowbits" not in t
    assert t["pkg.bitmap.Bitmap.grow"] == 0.95 and t["pkg.util.helper"] == 0.95
    assert t["pkg.bitmap.local"] == 0.90 and t["pkg.bitmap.Run.__init__"] == 0.90
    assert t["pkg.base.Container.size"] == 0.75, "unknown receiver, unique name"
    assert not any(k.startswith("os") for k in t), "external module: no typed edge"
    assert "pkg.other.util.lowbits" in cg.methods["pkg.bitmap.Bitmap.checked_add"].callees, "name superset"


def test_self_and_super_follow_the_class_hierarchy(cg):
    run_add = cg.methods["pkg.bitmap.Run.add"].typed_callees
    assert run_add == {"pkg.base.Container.add": 0.95}
    assert transitive_callers(cg, {"pkg.util.lowbits"}) >= {"pkg.bitmap.Bitmap.checked_add"}


def test_mixed_languages_are_refused():
    with pytest.raises(ValueError, match="one language"):
        build_call_graph({"a.py": "", "B.java": "class B {}"})
