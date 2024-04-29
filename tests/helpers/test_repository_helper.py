from unittest.mock import Mock, patch

import pytest
from github import UnknownObjectException

from src.helpers.repository_helper import get_repo_cached, get_repository


@pytest.mark.parametrize(
    "repository_name, repository_owner_login, expected",
    [
        (
            "repository_name",
            "owner_login",
            "owner_login/repository_name",
        ),  # repository found with owner and name
        ("repository_name", None, "repository_name"),  # repository found with name
        ("repository_name", None, None),  # repository not found
    ],
)
def test_get_repository(repository_name, repository_owner_login, expected, gh):
    if expected:  # if repository is expected to be found
        gh.get_repo.return_value = expected
    else:  # if repository is not expected to be found
        gh.get_repo.side_effect = UnknownObjectException(0)

    assert get_repository(gh, repository_name, repository_owner_login) == expected


@pytest.mark.parametrize(
    "repository_name, pass_gh",
    [
        ("repository_name", True),  # repository found
        ("repository_name", False),  # repository not found
    ],
)
def test_get_repo_cached(repository_name, pass_gh, gh):
    other_gh = Mock()
    with patch("src.helpers.repository_helper.github") as github:
        github.Github.return_value = other_gh
        get_repo_cached(repository_name, gh=gh if pass_gh else None)
    if pass_gh:
        gh.get_repo.assert_called_once_with(repository_name)
    else:
        other_gh.get_repo.assert_called_once_with(repository_name)
