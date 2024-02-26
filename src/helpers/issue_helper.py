import re
from typing import Optional

from github import Github
from github.Issue import Issue
from github.Repository import Repository

from src.helpers.repository_helper import get_repo_cached


def has_tasklist(issue_body: str) -> bool:
    """Return if the issue has a tasklist"""
    return bool(re.search(r"- \[(.)] (.*)", issue_body))


def get_tasklist(issue_body: str) -> dict[str, bool]:
    """Return the tasks in a tasklist in the issue body, if there is any"""
    tasks = {}
    for line in issue_body.split("\n"):
        if task := re.match(r"- \[(.)] (.*)", line):
            checked = task.group(1) == "x"
            task_info: str = task.group(2).strip()
            tasks[task_info] = checked
    return tasks


def issue_ref(created_issue):
    """Return an issue reference {owner}/{repo}#{issue_number}"""
    return f"{created_issue.repository.full_name}#{created_issue.number}"


def get_issue(gh: Github, repository: Repository, task: str) -> Optional[Issue]:
    """Get an Issue by the reference {owner}/{repo}#{issue_number}"""
    if "#" not in task:
        return None
    issue_repository, issue_number = task.split("#")
    if issue_repository:
        repository = get_repo_cached(gh, issue_repository)
    return repository.get_issue(int(issue_number))


def handle_issue_state(checked: bool, task_issue: Issue):
    """
    Handle the state of the issue.
    If the issue is closed and the checkbox is checked, open the issue.
    If the issue is open and the checkbox is unchecked, close the issue.
    """
    if checked:
        if task_issue.state == "open":
            task_issue.edit(state="closed")
            return True
    elif task_issue.state == "closed":
        task_issue.edit(state="open")
        return True
    return False
