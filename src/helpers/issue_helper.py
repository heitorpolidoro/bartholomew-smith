import re
from typing import Optional

from github import Github
from github.Issue import Issue
from github.Repository import Repository
from githubapp import Config
from src.helpers.repository_helper import get_repo_cached, get_repository


def has_tasklist(issue_body: str) -> bool:
    """Return if the issue has a tasklist"""
    return bool(re.search(r"- \[(.)] (.*)", issue_body))


def get_tasklist(issue_body: str) -> list[tuple[str, bool]]:
    """Return the tasks in a tasklist in the issue body, if there is any"""
    tasks = []
    for line in issue_body.split("\n"):
        if task := re.match(r"- \[(.)] (.*)", line):
            checked = task.group(1) == "x"
            task_info: str = task.group(2).strip()
            tasks.append((task_info, checked))
    return tasks


def get_issue_ref(issue):
    """Return an issue reference {owner}/{repo}#{issue_number}"""
    return f"{issue.repository.full_name}#{issue.number}"


def handle_issue_state(checked: bool, task_issue: Issue):
    """
    Handle the state of the issue.
    If the issue is closed and the checkbox is checked, open the issue.
    If the issue is open and the checkbox is unchecked, close the issue.
    """
    print("updating issue status")
    if checked:
        if task_issue.state == "open":
            task_issue.edit(state="closed")
            return True
    elif task_issue.state == "closed":
        task_issue.edit(state="open")
        return True
    return False


def update_issue_comment_status(issue, comment, issue_comment_id=None):
    if issue_comment_id:
        issue_comment = issue.get_comment(issue_comment_id)
        issue_comment.edit(comment)
        return issue_comment

    issue_comment = next(
        iter(ic for ic in issue.get_comments() if ic.user.login == Config.BOT_NAME),
        None,
    )
    if issue_comment:
        issue_comment.edit(comment)
        return issue_comment
    else:
        return issue.create_comment(comment)
