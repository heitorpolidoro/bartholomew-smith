"""Module to create the githubapp Configs"""

from typing import NoReturn

from githubapp import Config


def default_configs() -> NoReturn:
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
        auto_approve_logins=[],
        auto_update=True,
    )
    Config.create_config("release_manager", enabled=True)
    Config.create_config(
        "issue_manager",
        enabled=True,
        handle_tasklist=True,
        create_issues_from_tasklist=True,
        close_parent=True,
        close_subtasks=True,
        handle_checkbox=True,
    )
