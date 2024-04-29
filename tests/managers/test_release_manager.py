from unittest.mock import patch, Mock

import pytest

from src.helpers.release_helper import is_relative_release
from src.managers.release_manager import manage


@pytest.mark.parametrize(
    "is_default_branch,expected_version_to_release,commits_command,existing_pull_request",
    [
        [True, "", [""], True],
        [True, "1.0.0", ["1.0.0"], True],
        [True, "1.0.0", ["major"], True],
        [True, "invalid", ["invalid"], True],
        [False, "", [""], True],
        [False, "1.0.0", ["1.0.0"], True],
        [False, "", [""], False],
    ],
    ids=[
        "Default Branch with no command",
        "Default Branch with command",
        "Default Branch with relative release",
        "Default Branch with invalid relative",
        "No default Branch with no command",
        "No default Branch with command",
        "No Pull Request",
    ],
)
def test_manage(
    is_default_branch,
    expected_version_to_release,
    commits_command,
    existing_pull_request,
    event,
    repository,
    pull_request,
    check_run,
):
    commits_to_return = [
        Mock(commit=Mock(message=message)) for message in commits_command
    ]
    repository.compare().commits.reversed = commits_to_return
    pull_request.get_commits().reversed = commits_to_return
    if is_default_branch:
        event.check_suite.head_branch = "master"
    else:
        event.check_suite.head_branch = "branch"
    with (
        patch("src.managers.release_manager.command_helper") as command_helper,
        patch("src.managers.release_manager.release_helper") as release_helper,
        patch(
            "src.managers.release_manager.pull_request_helper.get_existing_pull_request"
        ) as get_existing_pull_request,
    ):
        release_helper.get_absolute_release.return_value = expected_version_to_release
        release_helper.is_relative_release = is_relative_release
        release_helper.is_valid_release = lambda x: x != "invalid"
        if existing_pull_request:
            get_existing_pull_request.return_value = pull_request
        else:
            get_existing_pull_request.return_value = None
        command_helper.get_command = lambda x, _: x
        manage(event)

        if not existing_pull_request:
            check_run.update.assert_called_once_with(
                title="No Pull Request found", conclusion="success"
            )
        elif not expected_version_to_release:
            check_run.update.assert_called_once_with(
                title="No release command found", conclusion="success"
            )
        elif expected_version_to_release == "invalid":
            check_run.update.assert_called_once_with(
                title=f"Invalid release invalid",
                summary="Invalid release ❌",
                conclusion="failure",
            )
        elif is_default_branch:
            repository.create_git_release.assert_called_once_with(
                tag=expected_version_to_release, generate_release_notes=True
            )
        else:
            repository.create_git_release.assert_not_called()
            check_run.update.assert_called_with(
                title=f"Ready to release {expected_version_to_release}",
                summary="Release command found ✅",
                conclusion="success",
            )

