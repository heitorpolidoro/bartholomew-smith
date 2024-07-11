from unittest.mock import patch, Mock

from githubapp import Config

from src.managers.pull_request_manager import get_title_and_body_from_issue


def test_when_disabled():
    with patch.object(
        Config.pull_request_manager,
        "link_issue",
        False,
    ):

        assert get_title_and_body_from_issue(None, None) == ("", "")


def test_when_branch_dont_match():
    assert get_title_and_body_from_issue(Mock(), "branch") == ("", "")


def test_when_branch_match():
    repository = Mock(full_name="repo_full_name")
    repository.get_issue.return_value = Mock(title="Match Title", body="Issue Body")
    assert get_title_and_body_from_issue(repository, "issue-42") == (
        "Match Title",
        """### [Match Title](https://github.com/repo_full_name/issues/42)

Issue Body

Closes #42

""",
    )


def test_when_branch_match_but_there_is_no_issue(repository):
    repository.get_issue.side_effect = Exception()
    assert get_title_and_body_from_issue(repository, "issue-42") == ("", "")


def test_when_branch_multiple_match(repository):
    repository.get_issue.side_effect = [
        Mock(title="Title 42", body="Body 42"),
        Mock(title="Title 14", body="Body 14"),
    ]
    assert get_title_and_body_from_issue(repository, "issue-42_issue-14") == (
        "Title 42",
        """### [Title 42](https://github.com/repo_full_name/issues/42)

Body 42

Closes #42

### [Title 14](https://github.com/repo_full_name/issues/14)

Body 14

Closes #14

""",
    )
