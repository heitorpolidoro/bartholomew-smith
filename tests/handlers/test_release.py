from src.handlers.release import handle_release


def test_handle_release(event, repository):
    handle_release(event)
    repository.get_commit.assert_called_once_with("sha")
    event.start_check_run.assert_called_once_with(
        "Releaser", "sha", title="Checking for release command"
    )
