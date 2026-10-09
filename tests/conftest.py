import pytest


def _energy_backend_available() -> bool:
    from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import _get_nemb_client

    return _get_nemb_client().lib is not None


def pytest_configure(config):
    config.addinivalue_line("markers", "needs_energy: requires a working NEMB energy backend (RAPL/MSR/NVML/IOReport)")


def pytest_collection_modifyitems(config, items):
    marked = [i for i in items if i.get_closest_marker("needs_energy")]
    if marked and not _energy_backend_available():
        skip = pytest.mark.skip(reason="no usable NEMB energy backend on this host")
        for i in marked:
            i.add_marker(skip)
