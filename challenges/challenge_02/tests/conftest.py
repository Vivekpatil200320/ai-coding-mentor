import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "broken_code"))

import main  # noqa: E402


@pytest.fixture(autouse=True)
def reset_state():
    main._todos.clear()
    main._next_id = 1
    yield
