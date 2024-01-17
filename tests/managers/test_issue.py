import pytest

from src.managers.issue import handle_tasklist

from unittest.mock import patch, Mock


@pytest.fixture(autouse=True)
def get_repository(repo_batata):
    def mocked_get_repository(_gh, repository_name, _owner):
        if repository_name == "repo_batata":
            return repo_batata

    with patch(
        "src.managers.issue.get_repository", side_effect=mocked_get_repository
    ) as mock:
        yield mock


@pytest.fixture
def repo_batata(created_issue):
    """
    This fixture returns a mock repository object with default values for the attributes.
    :return: Mocked Repository
    """
    repository = Mock(full_name="heitorpolidoro/repo_batata")
    repository.create_issue.return_value = created_issue
    return repository


@pytest.fixture
def created_issue(repository):
    created_issue = Mock(repository=repository)
    repository.create_issue.return_value = created_issue
    yield created_issue


def test_handle_tasklist_when_there_is_no_task_list(event, issue, repository):
    handle_tasklist(event)
    repository.create_issue.assert_not_called()
    issue.edit.assert_not_called()


def test_handle_tasklist_when_there_is_a_task_list(
    event, issue, repository, created_issue
):
    issue.body = "- [ ] batata"
    created_issue.number = 123
    handle_tasklist(event)
    repository.create_issue.assert_called_once_with(title="batata")
    issue.edit.assert_called_once_with(body="- [ ] heitorpolidoro/bartholomew-smith#123")


def test_handle_tasklist_with_just_repository_name(
    event, issue, repo_batata, created_issue
):
    issue.body = "- [ ] repo_batata"
    created_issue.number = 123
    created_issue.repository = repo_batata
    handle_tasklist(event)
    repo_batata.create_issue.assert_called_once_with(title="Issue Title")
    issue.edit.assert_called_once_with(body="- [ ] heitorpolidoro/repo_batata#123")


def test_handle_tasklist_with_repository_name_and_title(
    event, issue, repo_batata, created_issue
):
    issue.body = "- [ ] [repo_batata] Batata"
    created_issue.number = 123
    created_issue.repository = repo_batata
    handle_tasklist(event)
    repo_batata.create_issue.assert_called_once_with(title="Batata")
    issue.edit.assert_called_once_with(body="- [ ] heitorpolidoro/repo_batata#123")


def test_handle_tasklist_with_issue_in_task_list(event, issue, repository):
    issue.body = "- [x] #123"
    repository.get_issue.return_value = issue
    with patch("src.managers.issue.handle_issue_state") as handle_issue_state:
        handle_tasklist(event)
    handle_issue_state.assert_called_once_with(True, issue)
    repository.get_issue.assert_called_once_with(123)
    repository.create_issue.assert_not_called()
    issue.edit.assert_not_called()
