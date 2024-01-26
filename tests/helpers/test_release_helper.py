from unittest.mock import Mock

from github import UnknownObjectException

from src.helpers.release import (
    get_absolute_release,
    get_last_release,
    is_relative_release,
    is_valid_release,
)


def test_is_relative_release():
    assert is_relative_release("1.2.3") is False
    assert is_relative_release("major") is True


def test_is_valid_release():
    assert is_valid_release("1.2.3") is True


def test_get_relative_release():
    assert get_absolute_release("1.2.3", "major") == "2.0.0"
    assert get_absolute_release("1.2.3", "minor") == "1.3.0"
    assert get_absolute_release("1.2.3", "patch") == "1.2.4"
    assert get_absolute_release("1.2.3", "bugfix") == "1.2.4"

    assert get_absolute_release("0", "major") == "1"
    assert get_absolute_release("0", "minor") == "0.1"
    assert get_absolute_release("0", "bugfix") == "0.0.1"


def test_get_last_release(repository):
    repository.get_latest_release.return_value = Mock(tag_name="1.2.3")
    assert get_last_release(repository) == "1.2.3"


def test_get_last_release_when_there_is_no_release(repository):
    repository.get_latest_release.side_effect = UnknownObjectException(404)
    assert get_last_release(repository) == "0"
