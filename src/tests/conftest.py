import pytest

from spi_timing.config import load_setup
from spi_timing.instrument import Probe


@pytest.fixture(scope="session")
def setup():
    return load_setup()


@pytest.fixture(scope="module")
def probe(setup, request):
    """One instrument session and compiled pattern per test module, built for that module's SPEC."""
    spec = request.module.SPEC
    p = Probe(setup, sdo_expect=spec.sdo_expect, name=spec.symbol).open()
    yield p
    p.close()
