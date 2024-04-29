import pytest
from github import UnknownObjectException

from src.helpers.release_helper import (
    is_relative_release,
    is_valid_release,
    get_absolute_release,
    get_last_release,
)


@pytest.mark.parametrize(
    "version,expected",
    [
        ("major", True),
        ("minor", True),
        ("patch", True),
        ("bugfix", True),
        ("invalid", False),
        ("", False),
        ("major_minor", False),
        (None, False),
    ],
)
def test_is_relative_release(version, expected):
    assert is_relative_release(version) == expected


@pytest.mark.parametrize(
    "version,expected",
    [
        ("1.2.3", True),
        ("1.2", True),
        ("1", True),
        ("1.2.3.4", True),
        ("v1.2", False),
        ("1.v2", False),
        ("1.2v", False),
        ("1..2", False),
        ("", False),
        (None, False),
        ("1.2.3.", False),
        (".1.2.3", False),
    ],
)
def test_is_valid_release(version, expected):
    assert is_valid_release(version) == expected


@pytest.mark.parametrize(
    "last_release,relative_version,expected",
    [
        ("1.2.3", "major", "2.0.0"),
        ("1.2.3", "minor", "1.3.0"),
        ("1.2.3", "patch", "1.2.4"),
        ("2.0.0", "major", "3.0.0"),
        ("2", "major", "3"),
        ("2", "bugfix", "2.0.1"),
        ("2.0", "major", "3.0"),
        ("2.0.0", "major", "3.0.0"),
        ("1.2", "minor", "1.3"),
        ("1.2.3", "bugfix", "1.2.4"),
    ],
)
def test_get_absolute_release(last_release, relative_version, expected):
    assert get_absolute_release(last_release, relative_version) == expected


def test_get_last_release(repository):
    # test case when latest release exists
    repository.get_latest_release().tag_name = "v1.0.0"
    assert get_last_release(repository) == "v1.0.0"

    # test case when latest release does not exist
    repository.get_latest_release.side_effect = UnknownObjectException(0)
    assert get_last_release(repository) == "0"
