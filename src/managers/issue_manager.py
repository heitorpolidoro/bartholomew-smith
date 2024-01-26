import re

from githubapp.events import IssuesEvent

from src.helpers.issue_helper import get_issue, get_tasklist, handle_issue_state, issue_ref
from src.helpers.repository_helper import get_repository


def handle_tasklist(event: IssuesEvent):
    """
    Handle the tasklist in the issue.
    Create issues for each task in the tasklist following:
    - If the task is a valid repository name, create an issue in that repository with the same title as the
    original issue
    - If the task follows the pattern "[repository_name] issue title" create an issue in that repository
    with "issue title" as title
    - If none of above, create an issue in the same repository with "<task>" as title.

    Replace the task with the issue reference in the issue body.
    :param event:
    :return:
    """
    gh = event.gh
    repository = event.repository
    issue = event.issue
    issue_body = issue.body
    all_checked = []
    for checked, task in get_tasklist(issue_body):
        all_checked.append(checked)
        if task_issue := get_issue(gh, repository, task):
            handle_issue_state(checked, task_issue)

        else:
            if repository_and_title := re.match(r"\[(.+?)] (.+)", task):
                repository_name = repository_and_title.group(1)
                title = repository_and_title.group(2)
            else:
                repository_name = task
                title = issue.title

            issue_repository = get_repository(
                gh, repository_name, repository.owner.login
            )
            if issue_repository is None:
                issue_repository = repository
                title = task

            create_issue_params = {
                "title": title,
            }
            if issue.milestone is not None:
                create_issue_params["milestone"] = issue.milestone
            created_issue = issue_repository.create_issue(**create_issue_params)
            issue_body = issue_body.replace(task, issue_ref(created_issue))
    if issue_body != issue.body:
        issue.edit(body=issue_body)
    if all_checked and all(all_checked):
        issue.edit(state="closed")


def handle_close_tasklist(event: IssuesEvent):
    """
    Close all issues in the tasklist.
    :param event:
    :return:
    """
    gh = event.gh
    repository = event.repository
    issue = event.issue
    issue_body = issue.body
    for _, task in get_tasklist(issue_body):
        if task_issue := get_issue(gh, repository, task):
            if task_issue.state != "closed":
                task_issue.edit(state="closed", state_reason=issue.state_reason)