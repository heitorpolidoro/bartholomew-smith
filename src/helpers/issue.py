import re
from typing import Optional

from github import Github
from github.Issue import Issue
from github.Repository import Repository


def get_tasklist(issue_body: str) -> list[tuple[bool, str]]:
    tasks = []
    for line in issue_body.split("\n"):
        if task := re.match(r"- \[(.)] (.*)", line):
            tasks.append((task.group(1) == "x", task.group(2)))
    return tasks


def issue_ref(created_issue):
    return f"{created_issue.repository.full_name}#{created_issue.number}"


def get_issue(gh: Github, repository: Repository, task: str) -> Optional[Issue]:
    if "#" not in task:
        return None
    issue_repository, issue_number = task.split("#")
    if issue_repository:
        repository = gh.get_repo(issue_repository)
    return repository.get_issue(int(issue_number))


def handle_issue_state(checked, task_issue):
    """
    Handle the state of the issue.
    If the issue is closed and the checkbox is checked, open the issue.
    If the issue is open and the checkbox is unchecked, close the issue.
    :param checked:
    :param task_issue:
    """
    if checked:
        if task_issue.state == "open":
            task_issue.edit(state="closed")
    elif task_issue.state == "closed":
        task_issue.edit(state="open")
