import re
from collections import defaultdict

from githubapp.events import IssuesEvent

from src.helpers.issue_helper import (
    get_issue,
    get_tasklist,
    issue_ref,
    handle_issue_state,
)
from src.helpers.repository_helper import get_repository


# sqs = boto3.client("sqs", region_name="us-east-1")


# def handle_opened_or_edited_event(event: Union[IssueOpenedEvent, IssueEditedEvent]):
#     """
#     Handle the tasklist in the issue.
#     Create issues for each task in the tasklist following:
#     - If the task is a valid repository name, create an issue in that repository with the same title as the
#     original issue
#     - If the task follows the pattern "[repository_name] issue title" create an issue in that repository
#     with "issue title" as title
#     - If none of the above, create an issue in the same repository with "<task>" as title.
#
#     Replace the task with the issue reference in the issue body.
#     :param event:
#     :return:
#     """
#     issue = event.issue
#     issue_body = issue.body
#     if has_tasklist(issue_body):
#         issue_comment = issue.create_comment(
#             "I'll manage the issues in the next minutes (sorry, free server :disappointed: )"
#         )
#         sqs.send_message(
#             QueueUrl=os.getenv("TASKLIST_QUEUE"),
#             MessageBody={
#                 "issue": issue_ref(issue),
#                 "issue_comment_id": issue_comment.id,
#             },
#         )


def handle_task_list(gh, issue, issue_comment_id):
    def progress():
        return f"{count}/{total}\n![](https://geps.dev/progress/{int(count/total*100)}?dangerColor=006600&warningColor=006600&successColor=006600)"

    def summarize():
        body = ""
        if issues_updated := summary.get("issues_updated"):
            body += f"\nUpdated {issues_updated} issues"
        if issues_created := summary.get("issues_created"):
            body += f"\nCreated {issues_created} issues"
        return body

    issue = get_issue(gh, None, issue)
    issue_comment = issue.get_comment(issue_comment_id)
    issue_body = issue.body
    repository = issue.repository
    all_checked = []
    tasklist = get_tasklist(issue_body)
    total = len(tasklist)
    count = 0
    issue_comment.edit(f"Starting to manage the tasklist..\n{progress()}")
    summary = defaultdict(int)
    for task, checked in tasklist.items():
        all_checked.append(checked)
        if task_issue := get_issue(gh, repository, task):
            if handle_issue_state(checked, task_issue):
                summary["issues_updated"] += 1

        elif not checked:
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

            print(f"Creating issue {issue_repository.full_name}:{title}..")
            created_issue = issue_repository.create_issue(**create_issue_params)
            summary["issues_created"] += 1
            issue_body = issue_body.replace(
                f"- [ ] {task}", f"- [ ] {issue_ref(created_issue)}", 1
            )
        count += 1
        comment_body = (
            f"Analyzing the tasklist..\n{progress()}"
        )
        if summary:
            comment_body += "\n" + summarize()
        issue_comment.edit(comment_body)

    if issue_body != issue.body:
        issue.edit(body=issue_body)
    if all_checked and all(all_checked):
        issue.edit(state="closed")
    comment_body = "Tasklist analysis completed"
    if summary:
        comment_body += "\n" + summarize()
    issue_comment.edit(comment_body)


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
    for task in get_tasklist(issue_body).keys():
        if task_issue := get_issue(gh, repository, task):
            if task_issue.state != "closed":
                task_issue.edit(state="closed", state_reason=issue.state_reason)
