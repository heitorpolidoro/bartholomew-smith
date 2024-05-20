"""This module contains the logic for managing Github Issues."""

import logging
import re
from functools import lru_cache
from typing import NoReturn, Optional, TypeVar

import github
from github import Consts, UnknownObjectException
from github.Issue import Issue
from github.Repository import Repository
from github.Requester import Requester
from githubapp import Config
from githubapp.events import (
    IssueClosedEvent,
    IssueEditedEvent,
    IssueOpenedEvent,
    IssuesEvent,
)
from githubapp.webhook_handler import _get_auth

from src.helpers import issue_helper
from src.helpers.issue_helper import get_issue_ref, handle_issue_state
from src.helpers.repository_helper import get_repository
from src.helpers.text_helper import extract_repo_title, is_issue_ref, markdown_progress
from src.models import IssueJob, IssueJobStatus, Job, JobStatus
from src.services import IssueJobService, JobService

logger = logging.getLogger(__name__)
T = TypeVar("T")


def get_or_create_issue_job(event: IssuesEvent) -> IssueJob:
    """Get or create an issue job."""
    issue = event.issue
    if not (issue_job := next(iter(IssueJobService.filter(issue_url=issue.url)), None)):
        issue_comment = issue_helper.update_issue_comment_status(
            issue,
            "I'll manage the issues in the next minutes (sorry, free server :disappointed: )",
        )
        issue_comment_id = issue_comment.id
        issue_job = IssueJobService.insert_one(
            IssueJob(
                issue_url=issue.url,
                repository_url=issue.repository.url,
                title=issue.title,
                issue_comment_id=issue_comment_id,
                hook_installation_target_id=event.hook_installation_target_id,
                installation_id=event.installation_id,
                milestone_url=issue.milestone.url if issue.milestone else None,
            )
        )
    return issue_job


@Config.call_if("issue_manager.enabled")
def manage(event: IssuesEvent) -> Optional[IssueJob]:
    """Manage an issue or they task list."""
    issue = event.issue
    if issue_helper.has_tasklist(issue.body):
        if isinstance(event, (IssueOpenedEvent, IssueEditedEvent)):
            return handle_task_list(event)
        if isinstance(event, IssueClosedEvent):
            close_sub_tasks(event)
    return None


@Config.call_if("issue_manager.handle_tasklist")
def handle_task_list(event: IssuesEvent) -> Optional[IssueJob]:
    """Handle the task list of an issue."""
    issue = event.issue
    tasklist = issue_helper.get_tasklist(issue.body)
    existing_jobs = {}
    created_issues = {}
    for j in JobService.filter(original_issue_url=issue.url):
        existing_jobs[j.task] = j
        if j.issue_ref:
            created_issues[j.issue_ref] = j
    jobs = []

    for task, checked in tasklist:
        if task in existing_jobs:
            continue
        # issue created in a previous run
        if created_issue := created_issues.get(task):
            JobService.update(
                created_issue, checked=checked, job_status=JobStatus.PENDING
            )
        else:
            jobs.append(
                Job(
                    task=task,
                    original_issue_url=issue.url,
                    checked=checked,
                )
            )

    if jobs:
        JobService.insert_many(jobs)

    issue_job = get_or_create_issue_job(event)
    if issue_job.issue_job_status == IssueJobStatus.DONE:
        IssueJobService.update(issue_job, issue_job_status=IssueJobStatus.PENDING)
    return issue_job


@lru_cache
def _cached_get_auth(
    hook_installation_target_id: int, installation_id: int
) -> github.Auth:
    """Get the auth for the given installation, cached."""
    return _get_auth(hook_installation_target_id, installation_id)


@lru_cache
def _get_gh(hook_installation_target_id: int, installation_id: int) -> github.Github:
    """Get the Github object for the given installation, cached"""
    return github.Github(
        auth=_cached_get_auth(hook_installation_target_id, installation_id)
    )


@lru_cache
def _get_requester(hook_installation_target_id: int, installation_id: int) -> Requester:
    """Get the Requester object for the given installation, cached"""
    return Requester(
        auth=_cached_get_auth(hook_installation_target_id, installation_id),
        base_url=Consts.DEFAULT_BASE_URL,
        timeout=Consts.DEFAULT_TIMEOUT,
        user_agent=Consts.DEFAULT_USER_AGENT,
        per_page=Consts.DEFAULT_PER_PAGE,
        verify=True,
        retry=github.GithubRetry(),
        pool_size=None,
    )


@lru_cache
def _get_repository(issue_job: IssueJob, repository_name: str) -> Repository:
    """Get the Repository object for the given installation, cached"""
    gh = _get_gh(
        issue_job.hook_installation_target_id,
        issue_job.installation_id,
    )
    if "/" not in repository_name:
        owner = issue_job.repository_url.split("/")[-2]
        repository_name = f"{owner}/{repository_name}"
    return get_repository(gh, repository_name)


@lru_cache
def _instantiate_github_class(
    clazz: type[T], hook_installation_target_id: int, installation_id: int, url: str
) -> T:
    """Instantiate a Github class, cached"""
    return clazz(
        requester=_get_requester(hook_installation_target_id, installation_id),
        headers={},
        attributes={"url": url},
        completed=False,
    )


def set_jobs_to_done(jobs: list[Job], issue_job: IssueJob) -> NoReturn:
    """Set the jobs to done."""
    for job in jobs:
        JobService.update(job, job_status=JobStatus.DONE)
    process_update_progress(issue_job)


def process_jobs(issue_url: str) -> Optional[IssueJobStatus]:
    """Process the jobs."""
    if issue_job := next(iter(IssueJobService.filter(issue_url=issue_url)), None):
        if issue_job.issue_job_status == IssueJobStatus.PENDING:
            IssueJobService.update(issue_job, issue_job_status=IssueJobStatus.RUNNING)
            # Update not updated jobs
            process_update_issue_body(issue_job)
            process_pending_jobs(issue_job)
            process_update_issue_status(issue_job)
            process_create_issue(issue_job)
            process_update_issue_body(issue_job)
            close_issue_if_all_checked(issue_job)
            IssueJobService.update(issue_job, issue_job_status=IssueJobStatus.DONE)
            process_update_progress(issue_job)
            return IssueJobStatus.DONE
        return issue_job.issue_job_status
    return None


def _repository_url(repository: str) -> str:
    """Get the repository url."""
    return f"{Consts.DEFAULT_BASE_URL}/repos/{repository}"


def _get_repository_url_and_title(issue_job: IssueJob, task: str) -> tuple[str, str]:
    """Get the title and repository url from the issue job os task."""
    title = issue_job.title
    repository_url = issue_job.repository_url
    if repo_title := extract_repo_title(task):
        repository, task_title = repo_title
        if "/" in repository:
            repository_url = _repository_url(repository)
        else:
            repository_url = "/".join(repository_url.split("/")[:-1] + [repository])
        if task_title:
            title = task_title
    else:
        if " " not in task and (task_repository := _get_repository(issue_job, task)):
            repository_url = task_repository.url
        else:
            title = task
    return repository_url, title


def process_pending_jobs(issue_job: IssueJob) -> NoReturn:
    """Process the pending jobs separating what is a job to create an issue from a job to update an issue"""
    for job in JobService.filter(
        original_issue_url=issue_job.issue_url, job_status=JobStatus.PENDING
    ):
        task = job.task
        if job.issue_ref or is_issue_ref(task):
            issue_ref = job.issue_ref or task
            repository, issue_number = issue_ref.split("#")
            if repository:
                repository_url = _repository_url(repository)
            else:
                repository_url = issue_job.repository_url
            issue_url = f"{repository_url}/issues/{issue_number}"
            JobService.update(
                job,
                job_status=JobStatus.UPDATE_ISSUE_STATUS,
                issue_url=issue_url,
            )
        else:
            repository_url, title = _get_repository_url_and_title(issue_job, task)

            JobService.update(
                job,
                job_status=JobStatus.CREATE_ISSUE,
                repository_url=repository_url,
                title=title,
            )


def process_update_issue_status(issue_job: IssueJob) -> NoReturn:
    """Process the update issue status jobs."""
    for job in JobService.filter(
        original_issue_url=issue_job.issue_url, job_status=JobStatus.UPDATE_ISSUE_STATUS
    ):
        issue = _instantiate_github_class(
            Issue,
            issue_job.hook_installation_target_id,
            issue_job.installation_id,
            job.issue_url,
        )
        try:
            _handle_checkbox(issue, job.checked)
            JobService.update(
                job,
                job_status=JobStatus.DONE,
            )
        except UnknownObjectException:
            logger.warning("Issue %s not found", issue.url)
            JobService.update(job, job_status=JobStatus.ERROR)


@Config.call_if("issue_manager.handle_checkbox")
def _handle_checkbox(issue: Issue, checked: bool) -> NoReturn:
    """
    Handle the state of the issue.
    If the issue is closed and the checkbox is checked, open the issue.
    If the issue is open and the checkbox is unchecked, close the issue.
    """
    handle_issue_state(checked, issue)


def process_create_issue(issue_job: IssueJob) -> NoReturn:
    """Process the create_issue status jobs."""
    for job in JobService.filter(
        original_issue_url=issue_job.issue_url, job_status=JobStatus.CREATE_ISSUE
    ):
        if created_issue := _create_issue(issue_job, job):
            JobService.update(
                job,
                job_status=JobStatus.UPDATE_ISSUE_BODY,
                issue_ref=get_issue_ref(created_issue),
            )
        else:
            JobService.update(
                job,
                job_status=JobStatus.DONE,
            )


@Config.call_if("issue_manager.create_issues_from_tasklist")
def _create_issue(issue_job: IssueJob, job: Job) -> Issue:
    """Create a new issue."""
    repository = _instantiate_github_class(
        Repository,
        issue_job.hook_installation_target_id,
        issue_job.installation_id,
        job.repository_url,
    )
    created_issue = repository.create_issue(title=job.title)
    return created_issue


def process_update_issue_body(issue_job: IssueJob) -> NoReturn:
    """Process the update issue body jobs."""
    issue = _instantiate_github_class(
        Issue,
        issue_job.hook_installation_target_id,
        issue_job.installation_id,
        issue_job.issue_url,
    )
    body = issue.body
    update_issue_body_jobs = JobService.filter(
        original_issue_url=issue_job.issue_url, job_status=JobStatus.UPDATE_ISSUE_BODY
    )
    for job in update_issue_body_jobs:
        body = re.sub(
            r"(\[[ x]]) " + job.task + r"(?=\s|$)",
            f"\\1 {job.issue_ref}",
            body,
        )
    issue.edit(body=body)
    set_jobs_to_done(update_issue_body_jobs, issue_job)


@Config.call_if("issue_manager.close_parent")
def close_issue_if_all_checked(issue_job: IssueJob) -> NoReturn:
    """Close the issue if all the tasks are checked."""
    issue = _instantiate_github_class(
        Issue,
        issue_job.hook_installation_target_id,
        issue_job.installation_id,
        issue_job.issue_url,
    )
    issue_body = issue.body
    if issue_helper.has_tasklist(issue_body):
        tasklist = issue_helper.get_tasklist(issue_body)
        if tasklist and all(checked for _, checked in tasklist):
            issue.edit(state="closed")


def process_update_progress(issue_job: IssueJob) -> NoReturn:
    """Update the progress in the issue comment."""
    if issue_job.issue_job_status == IssueJobStatus.DONE:
        comment = "Job's done"
    else:
        done = len(
            JobService.filter(
                original_issue_url=issue_job.issue_url, job_status=JobStatus.DONE
            )
        )
        total = len(JobService.filter(original_issue_url=issue_job.issue_url))
        comment = (
            f"Analyzing the tasklist [{done}/{total}]\n{markdown_progress(done, total)}"
        )
    issue = _instantiate_github_class(
        Issue,
        issue_job.hook_installation_target_id,
        issue_job.installation_id,
        issue_job.issue_url,
    )
    issue_helper.update_issue_comment_status(
        issue,
        comment,
        issue_comment_id=issue_job.issue_comment_id,
    )


@Config.call_if("issue_manager.close_subtasks")
def close_sub_tasks(event: IssuesEvent) -> NoReturn:
    """Close all issues in the tasklist."""
    repository = event.repository
    issue = event.issue
    issue_body = issue.body
    for task, _ in issue_helper.get_tasklist(issue_body):
        if is_issue_ref(task):
            issue_repository, issue_number = task.split("#")
            if issue_repository:
                repository_url = _repository_url(issue_repository)
            else:
                repository_url = repository.url
            issue_url = f"{repository_url}/issues/{issue_number}"
            task_issue = _instantiate_github_class(
                Issue,
                event.hook_installation_target_id,
                event.installation_id,
                issue_url,
            )
            try:
                if task_issue.state != "closed":
                    task_issue.edit(state="closed", state_reason=issue.state_reason)
            except UnknownObjectException:
                logger.warning("Issue %s not found", issue.url)
