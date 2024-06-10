from unittest.mock import Mock

import pytest


@pytest.fixture
def pull_request():
    return Mock(number=123)


@pytest.fixture
def gh():
    return Mock()
