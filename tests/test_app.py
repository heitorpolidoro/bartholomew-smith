from unittest.mock import patch

from app import handle, sentry_init


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
    with patch("app.handle_create_pull_request") as mock_handle_create_pull_request:
        handle(event)
        mock_handle_create_pull_request.assert_called_once_with(
            repository, event.check_suite.head_branch
        )
