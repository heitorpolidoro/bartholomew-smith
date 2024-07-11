"""Module to create the githubapp Configs"""

from githubapp import Config, EventCheckRun


def default_configs() -> None:
    """Create the default configs"""
    Config.BOT_NAME = "bartholomew-smith[bot]"
    Config.TIMEOUT = "8"

    Config.create_config(
        "pull_request_manager",
        enabled=True,
        create_pull_request=True,
        link_issue=True,
        enable_auto_merge=True,
        merge_method="SQUASH",
        auto_update=True,
        auto_approve=False,
        auto_approve_logins=[],
    )
    Config.create_config("release_manager", enabled=True, update_in_file=False)
    Config.create_config(
        "issue_manager",
        enabled=True,
        handle_tasklist=True,
        create_issues_from_tasklist=True,
        close_parent=True,
        close_subtasks=True,
        handle_checkbox=True,
    )
