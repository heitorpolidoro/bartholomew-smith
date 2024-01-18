from unittest import TestCase
from unittest.mock import patch

import markdown
import pytest
from githubapp.events.issues import IssueClosedEvent

from app import (
    app,
    handle_check_suite_requested,
    handle_issue,
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


def test_handle_check_suite_requested(event, repository):
    with (
        patch("app.handle_create_pull_request") as mock_handle_create_pull_request,
        patch("app.handle_release") as mock_handle_release,
    ):
        handle_check_suite_requested(event)
        mock_handle_create_pull_request.assert_called_once_with(
            repository, event.check_suite.head_branch
        )
        mock_handle_release.assert_called_once_with(event)


def test_handle_issue(event):
    with patch("app.handle_tasklist") as mock_handle_tasklist:
        handle_issue(event)
    mock_handle_tasklist.assert_called_once_with(event)


def test_handle_issue_when_issue_has_no_body(event, issue):
    issue.body = None
    with patch("app.handle_tasklist") as mock_handle_tasklist:
        handle_issue(event)
    mock_handle_tasklist.assert_not_called()


def test_handle_close_issue(event, issue):
    event.__class__ = IssueClosedEvent
    with patch("app.handle_close_tasklist") as mock_handle_close_tasklist:
        handle_issue(event)
    mock_handle_close_tasklist.assert_called_once_with(event)


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

    def test_file(self):
        response = self.client.get("/pull-request.md")
        assert response.status_code == 200
        with open("pull-request.md") as f:
            md = f.read()
        body = markdown.markdown(md)
        self.mock_render_template.assert_called_once_with(
            "index.html", title="Bartholomew Smith - Pull Request", body=body
        )

    def test_file_security(self):
        response = self.client.get("/other.txt")
        assert response.status_code == 404
        self.mock_render_template.assert_not_called()
