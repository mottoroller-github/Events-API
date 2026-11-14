import pytest

BASE_URL = "http://localhost:5000"


@pytest.fixture
def base_url():
    return BASE_URL
