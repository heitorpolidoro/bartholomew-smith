from unittest import TestCase
from unittest.mock import Mock, patch

import markdown
import pytest
from githubapp import Config

from app import (
    app,
    handle_check_suite_completed,
    handle_check_suite_requested,
    handle_issue,
    handle_issue_closed,
    sentry_init,
)


def test_sentry_init(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://example.com")
    with patch("app.sentry_sdk") as mock_sentry:
        sentry_init()
        mock_sentry.init.assert_called_once_with(
            dsn="https://example.com",
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )


def test_sentry_dont_init(monkeypatch):
    with patch("app.sentry_sdk") as mock_sentry:
        sentry_init()
        mock_sentry.init.assert_not_called()


@pytest.fixture
def handle_create_pull_request_mock():
    with patch("app.handle_create_pull_request") as handle_create_pull_request_mock:
        yield handle_create_pull_request_mock


@pytest.fixture
def handle_release_mock():
    with patch("app.handle_release") as handle_release_mock:
        yield handle_release_mock


@pytest.fixture
def handle_tasklist_mock():
    with patch("app.handle_tasklist") as handle_tasklist_mock:
        yield handle_tasklist_mock


@pytest.fixture
def handle_close_tasklist_mock():
    with patch("app.handle_close_tasklist") as handle_close_tasklist_mock:
        yield handle_close_tasklist_mock


@pytest.fixture
def handle_self_approver_mock():
    with patch("app.handle_self_approver") as handle_self_approver_mock:
        yield handle_self_approver_mock


def test_handle_check_suite_requested(
    event, repository, handle_create_pull_request_mock, handle_release_mock
):
    handle_check_suite_requested(event)
    handle_create_pull_request_mock.assert_called_once_with(
        repository, event.check_suite.head_branch
    )
    handle_release_mock.assert_called_once_with(event)


def test_handle_issue_opened_or_edited(event, handle_tasklist_mock):
    handle_issue(event)
    handle_tasklist_mock.assert_called_once_with(event)


def test_handle_issue_opened_or_edited_when_issue_has_no_body(
    event, issue, handle_tasklist_mock
):
    issue.body = None
    handle_issue(event)
    handle_tasklist_mock.assert_not_called()


def test_handle_issue_closed(event, issue, handle_close_tasklist_mock):
    handle_issue_closed(event)
    handle_close_tasklist_mock.assert_called_once_with(event)


def test_handle_issue_closed_when_issue_has_no_body(
    event, issue, handle_close_tasklist_mock
):
    issue.body = None
    handle_issue_closed(event)
    handle_close_tasklist_mock.assert_not_called()


def test_handle_check_suite_completed(
    event, repository, pull_request, monkeypatch, handle_self_approver_mock
):
    monkeypatch.setenv("OWNER_PAT", "gh_owner_pat")
    check_suite = event.check_suite
    check_suite.pull_requests = [pull_request]
    handle_check_suite_completed(event)
    handle_self_approver_mock.assert_called_once_with(
        "gh_owner_pat", repository, pull_request
    )


def test_handle_check_suite_completed_when_there_is_no_owner_pat(
    event, repository, pull_request, monkeypatch, handle_self_approver_mock
):
    monkeypatch.delenv("OWNER_PAT", False)
    handle_check_suite_completed(event)
    handle_self_approver_mock.assert_not_called()


@pytest.mark.usefixtures("mock_render_template")
class TestApp(TestCase):
    @pytest.fixture
    def mock_render_template(self):
        with patch("app.render_template") as mock_render_template:
            self.mock_render_template = mock_render_template
            yield mock_render_template

    def setUp(self):
        self.app = app
        self.client = app.test_client()

    def test_index(self):
        response = self.client.get("/")
        assert response.status_code == 200
        with open("README.md") as f:
            md = f.read()
        body = markdown.markdown(md)
        self.mock_render_template.assert_called_once_with(
            "index.html", title="Bartholomew Smith", body=body
        )

    def test_marketplace(self):
        response = self.client.post("/marketplace", json={1:2})
        assert response.status_code == 200


def test_managers_disabled(
    handle_create_pull_request_mock,
    handle_release_mock,
    handle_tasklist_mock,
    handle_close_tasklist_mock,
):
    event = Mock()
    with patch("app.Config.load_config_from_file"):
        Config.pull_request_manager.enabled = False
        Config.release_manager.enabled = False
        Config.issue_manager.enabled = False

    handle_check_suite_requested(event)
    handle_create_pull_request_mock.assert_not_called()
    handle_release_mock.assert_not_called()
    handle_issue(event)
    handle_tasklist_mock.assert_not_called()
    handle_issue_closed(event)
    handle_close_tasklist_mock.assert_not_called()
    Config.pull_request_manager.enabled = True
    Config.release_manager.enabled = True
    Config.issue_manager.enabled = True
