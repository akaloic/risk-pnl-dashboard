from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def use_fixture_data(monkeypatch):
    """Point every test at tests/fixtures/ instead of the real extracts.

    Autouse and unconditional: the suite must pass on a fresh clone that has no
    data/ directory at all, and no test should ever be able to reach the
    confidential files by accident.
    """
    monkeypatch.setenv("RAD_DATA_DIR", str(FIXTURES_DIR))
