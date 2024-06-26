"""Methods to helps with Github Issues"""

import re
from typing import Optional

from github.Issue import Issue
from github.IssueComment import IssueComment
from githubapp import Config


def has_tasklist(issue_body: str) -> bool:
    """Return if the issue has a tasklist"""
    return bool(issue_body) and bool(re.search(r"- \[(.)] (.*)", issue_body))


def get_tasklist(issue_body: str) -> list[tuple[str, bool]]:
    """Return the tasks in a tasklist in the issue body, if there is any"""
    tasks = []
    for line in issue_body.split("\n"):
        if task := re.match(r"- \[(.)] (.*)", line):
            checked = task.group(1) == "x"
            task_info: str = task.group(2).strip()
            tasks.append((task_info, checked))
    return tasks


def get_issue_ref(issue: Issue) -> str:
    """Return an issue reference {owner}/{repo}#{issue_number}"""
    return f"{issue.repository.full_name}#{issue.number}"


def handle_issue_state(checked: bool, task_issue: Issue) -> bool:
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


def update_issue_comment_status(issue: Issue, comment: str, issue_comment_id: Optional[int] = None) -> IssueComment:
    """Update a github issue comment. If `issue_commend_id` is None, create a new github issue comment"""
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
    return issue.create_comment(comment)
