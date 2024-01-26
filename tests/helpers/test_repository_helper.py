from unittest.mock import Mock, call

from github import UnknownObjectException

from src.helpers.repository_helper import get_repository


def test_get_repository():
    gh = Mock()
    repository = Mock()
    gh.get_repo.return_value = repository
    assert get_repository(gh, "batata") == repository
    gh.get_repo.assert_called_once_with("batata")


def test_get_repository_not_found():
    gh = Mock()
    gh.get_repo.side_effect = UnknownObjectException(404)
    assert get_repository(gh, "batata") is None
    gh.get_repo.assert_called_once_with("batata")


def test_get_repository_partial_name():
    gh = Mock()
    repository = Mock()

    def get_repo(name):
        if name == "owner/batata":
            return repository
        raise UnknownObjectException(404)

    gh.get_repo.side_effect = get_repo
    assert get_repository(gh, "batata", "owner") is repository
    gh.get_repo.assert_has_calls([call("batata"), call("owner/batata")])
