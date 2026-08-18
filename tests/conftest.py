from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def use_fixture_data(monkeypatch):
    """Point every test at tests/fixtures/ instead of the real extracts.

    Autouse and unconditional: the suite must pass on a fresh clone that has no
    data/ directory at all, and no test should ever be able to reach the
    confidential files by accident.

    The API caches its dataset for the life of the process, so that cache is
    dropped around every test as well -- otherwise the first test to hit an
    endpoint would pin the data every later test sees.
    """
    monkeypatch.setenv("RAD_DATA_DIR", str(FIXTURES_DIR))

    from app.main import reset_dataset_cache

    reset_dataset_cache()
    yield
    reset_dataset_cache()
