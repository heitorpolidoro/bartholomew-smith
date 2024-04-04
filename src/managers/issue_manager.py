import re
from functools import lru_cache

from github import Consts, Github, GithubRetry
from github.Auth import Auth
from github.Issue import Issue
from github.Repository import Repository
from github.Requester import Requester
from githubapp.events import IssuesEvent
from githubapp.webhook_handler import _get_auth

from src.helpers import issue_helper
from src.helpers.issue_helper import get_issue_ref, handle_issue_state
from src.helpers.repository_helper import get_repository
from src.helpers.text_helper import (
    extract_repo_title,
    is_issue_ref,
    is_repo_title_syntax,
    markdown_progress,
)
from src.models import IssueJob, IssueJobStatus, Job, JobStatus
from src.services import IssueJobService, JobService


def parse_issue_and_create_jobs(issue, hook_installation_target_id, installation_id):
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
                hook_installation_target_id=hook_installation_target_id,
                installation_id=installation_id,
                milestone_url=issue.milestone.url if issue.milestone else None,
            )
        )
    reediting = issue_job.issue_job_status == IssueJobStatus.DONE
    existing_jobs = {}
    if reediting:
        IssueJobService.update(issue_job, issue_job_status=IssueJobStatus.PENDING)
    else:
        for j in JobService.filter(original_issue_url=issue.url):
            existing_jobs[j.task] = j
            if j.issue_ref:
                existing_jobs[j.issue_ref] = j
    jobs = []

    for task, checked in issue_helper.get_tasklist(issue.body):
        if task in existing_jobs:
            continue
        if created_issue := next(iter(JobService.filter(original_issue_url=issue.url, issue_ref=task)), None):
            JobService.update(created_issue, checked=checked, job_status=JobStatus.PENDING)
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
    return issue_job


@lru_cache
def _cached_get_auth(hook_installation_target_id, installation_id) -> Auth:
    return _get_auth(hook_installation_target_id, installation_id)


@lru_cache
def _get_gh(hook_installation_target_id, installation_id) -> Github:
    auth = _cached_get_auth(hook_installation_target_id, installation_id)
    return Github(auth=auth)


@lru_cache
def _get_requester(hook_installation_target_id, installation_id):
    auth = _cached_get_auth(hook_installation_target_id, installation_id)
    return Requester(
        auth=auth,
        base_url=Consts.DEFAULT_BASE_URL,
        timeout=Consts.DEFAULT_TIMEOUT,
        user_agent=Consts.DEFAULT_USER_AGENT,
        per_page=Consts.DEFAULT_PER_PAGE,
        verify=True,
        retry=GithubRetry(),
        pool_size=None,
    )


@lru_cache
def _get_repository(issue_job: IssueJob, repository_name) -> Repository:
    gh = _get_gh(
        issue_job.hook_installation_target_id,
        issue_job.installation_id,
    )
    if "/" not in repository_name:
        owner = issue_job.repository_url.split("/")[-2]
        repository_name = f"{owner}/{repository_name}"
    return get_repository(gh, repository_name)


@lru_cache
def _instantiate_github_class(clazz, hook_installation_target_id, installation_id, url):
    return clazz(
        requester=_get_requester(hook_installation_target_id, installation_id),
        headers={},
        attributes={"url": url},
        completed=False,
    )


def set_jobs_to_done(jobs: list[Job], issue_job: IssueJob):
    for job in jobs:
        JobService.update(job, job_status=JobStatus.DONE)
    process_update_progress(issue_job)


def process_jobs(issue_url):
    issue_job_filter = IssueJobService.filter(issue_url=issue_url)
    if not issue_job_filter:
        return None
    issue_job = issue_job_filter[0]
    if issue_job.issue_job_status == IssueJobStatus.PENDING:
        IssueJobService.update(issue_job, issue_job_status=IssueJobStatus.RUNNING)
        process_update_issue_body(issue_job)  # Update not updated jobs
        process_pending_jobs(issue_job)
        process_update_issue_status(issue_job)
        process_create_issue(issue_job)
        process_update_issue_body(issue_job)
        close_issue_if_all_checked(issue_job)
        IssueJobService.update(issue_job, issue_job_status=IssueJobStatus.DONE)
        process_update_progress(issue_job)
        return IssueJobStatus.DONE
    return issue_job.issue_job_status


def _repository_url(repository):
    return f"{Consts.DEFAULT_BASE_URL}/repos/{repository}"


def _get_title_and_repository_url(issue_job, task):
    title = issue_job.title
    repository_url = issue_job.repository_url
    if is_repo_title_syntax(task):
        repository, task_title = extract_repo_title(task)
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


def process_pending_jobs(issue_job):
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
                job, job_status=JobStatus.UPDATE_ISSUE_STATUS, issue_url=issue_url,
            )
        else:
            repository_url, title = _get_title_and_repository_url(issue_job, task)

            JobService.update(
                job,
                job_status=JobStatus.CREATE_ISSUE,
                repository_url=repository_url,
                title=title,
            )


def process_update_issue_status(issue_job):
    for job in JobService.filter(
        original_issue_url=issue_job.issue_url, job_status=JobStatus.UPDATE_ISSUE_STATUS
    ):
        issue = Issue(
            requester=_get_requester(
                issue_job.hook_installation_target_id, issue_job.installation_id
            ),
            headers={},
            attributes={"url": job.issue_url},
            completed=False,
        )
        handle_issue_state(job.checked, issue)
        set_jobs_to_done([job], issue_job)


def process_create_issue(issue_job):
    for job in JobService.filter(
        original_issue_url=issue_job.issue_url, job_status=JobStatus.CREATE_ISSUE
    ):
        repository = _instantiate_github_class(
            Repository,
            issue_job.hook_installation_target_id,
            issue_job.installation_id,
            job.repository_url,
        )
        # TODO milestone
        created_issue = repository.create_issue(title=job.title)
        JobService.update(
            job,
            job_status=JobStatus.UPDATE_ISSUE_BODY,
            issue_ref=get_issue_ref(created_issue),
        )


def process_update_issue_body(issue_job):
    if update_issue_body_jobs := JobService.filter(
        original_issue_url=issue_job.issue_url, job_status=JobStatus.UPDATE_ISSUE_BODY
    ):
        issue = _instantiate_github_class(
            Issue,
            issue_job.hook_installation_target_id,
            issue_job.installation_id,
            issue_job.issue_url,
        )
        body = issue.body
        for job in update_issue_body_jobs:
            body = re.sub(
                rf"(\[[ x]]) {job.task}(?=\s|$)",
                f"\\1 {job.issue_ref}",
                body,
            )
        issue.edit(body=body)
        set_jobs_to_done(update_issue_body_jobs, issue_job)


def close_issue_if_all_checked(issue_job):
    issue = _instantiate_github_class(
        Issue,
        issue_job.hook_installation_target_id,
        issue_job.installation_id,
        issue_job.issue_url,
    )
    if all(checked for _, checked in issue_helper.get_tasklist(issue.body)):
        issue.edit(state="closed")


def process_update_progress(issue_job):
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
            if task_issue.state != "closed":
                task_issue.edit(state="closed", state_reason=issue.state_reason)
