import re
import time
from functools import lru_cache

from github import Github, Issue
from github.Repository import Repository
from githubapp.events import IssuesEvent
from githubapp.webhook_handler import _get_auth

from src.helpers import issue_helper
from src.helpers.issue_helper import get_issue, handle_issue_state, get_issue_ref
from src.helpers.repository_helper import get_repository
from src.helpers.text_helper import (
    is_issue_ref,
    is_repo_title_syntax,
    extract_repo_title,
    markdown_progress,
)
from src.models import Job, JobStatus
from src.services import JobService


def parse_issue_and_create_tasks(issue, hook_installation_target_id, installation_id):
    issue_comment = issue_helper.update_issue_comment_status(
        issue,
        "I'll manage the issues in the next minutes (sorry, free server :disappointed: )",
    )
    tasks = []
    issue_ref = issue_helper.get_issue_ref(issue)
    title = issue.title
    issue_comment_id = issue_comment.id
    for task, checked in issue_helper.get_tasklist(issue.body):
        tasks.append(
            Job(
                task=task,
                original_issue_ref=issue_ref,
                original_issue_title=title,
                checked=checked,
                issue_comment_id=issue_comment_id,
                hook_installation_target_id=hook_installation_target_id,
                installation_id=installation_id,
            )
        )
    if tasks:
        JobService.insert_many(tasks)


@lru_cache
def _get_gh(hook_installation_target_id, installation_id) -> Github:
    auth = _get_auth(hook_installation_target_id, installation_id)
    return Github(auth=auth)


@lru_cache
def _get_repository(_gh, repository_name, owner="") -> Repository:
    if "/" not in repository_name:
        repository_name = f"{owner}/{repository_name}"
    return get_repository(_gh, repository_name)


@lru_cache
def _get_original_issue(_gh, original_issue_ref) -> Issue:
    repository_name, issue_number = original_issue_ref.split("#")
    return _get_repository(_gh, repository_name).get_issue(int(issue_number))


def update_issue_body(original_issue, job):
    body = re.sub(
        rf"(\[[ x]]) {job.task}(?=\s\D)", f"\\1 {job.issue_ref}", original_issue.body
    )
    original_issue.edit(body=body)


def update_progress(gh, original_issue_ref, issue_comment_id):
    pending = len(
        JobService.filter(original_issue_ref=original_issue_ref, job_status="pending")
    )
    total = len(JobService.filter(original_issue_ref=original_issue_ref))
    count = total - pending
    comment = (
        f"Analyzing the tasklist [{count}/{total}]\n{markdown_progress(count, total)}"
    )
    issue = _get_original_issue(gh, original_issue_ref)
    issue_helper.update_issue_comment_status(
        issue,
        comment,
        issue_comment_id=issue_comment_id,
    )


def process_jobs():
    stop = False
    for job in JobService.all():
        start_total = time.time()
        start = time.time()
        if job.job_status == JobStatus.DONE:
            continue
        gh = _get_gh(
            job.hook_installation_target_id,
            job.installation_id,
        )
        original_issue = _get_original_issue(gh, job.original_issue_ref)
        print("before", round(time.time() - start, 2))
        if job.job_status == JobStatus.PENDING:
            start = time.time()
            process_job(job, original_issue, gh)
            print("process_job", round(time.time() - start, 2))
        if job.job_status == JobStatus.UPDATE_ISSUE_BODY:
            start = time.time()
            update_issue_body(original_issue, job)
            print("update_issue_body", round(time.time() - start, 2))
            stop = True
        start = time.time()
        JobService.to_done(job)
        update_progress(gh, job.original_issue_ref, job.issue_comment_id)
        print("update_progress", round(time.time() - start, 2))
        print("total", round(time.time() - start_total, 2))
        if stop:
            break


def process_job(job, original_issue, gh):
    task = job.task

    repository = original_issue.repository
    title = original_issue.title
    if is_issue_ref(task):
        issue = get_issue(gh, repository, task)
        handle_issue_state(job.checked, issue)
    else:
        if is_repo_title_syntax(task):
            repo, task_title = extract_repo_title(task)
            repository = _get_repository(gh, repo, owner=repository.owner.login)
            if task_title:
                title = task_title
        else:
            if " " not in task and (
                task_repository := _get_repository(
                    gh, task, owner=repository.owner.login
                )
            ):
                repository = task_repository
            else:
                title = task

        create_issue_params = {"title": title}
        if original_issue.milestone is not None:
            create_issue_params["milestone"] = original_issue.milestone
        created_issue = repository.create_issue(**create_issue_params)
        job.issue_ref = get_issue_ref(created_issue)
        job.job_status = JobStatus.UPDATE_ISSUE_BODY
        JobService.update(job)


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
    for task in issue_helper.get_tasklist(issue_body).keys():
        if task_issue := issue_helper.get_issue(gh, repository, task):
            if task_issue.state != "closed":
                task_issue.edit(state="closed", state_reason=issue.state_reason)
