import random
from unittest.mock import patch, Mock, ANY, call

import pytest
from github import Consts, UnknownObjectException
from githubapp.events import IssueOpenedEvent, IssueEditedEvent
from githubapp.events.issues import IssueClosedEvent

from src.helpers.text_helper import markdown_progress
from src.managers.issue_manager import (
    get_or_create_issue_job,
    manage,
    handle_task_list,
    process_jobs,
    process_pending_jobs,
    _get_title_and_repository_url,
    _get_repository,
    _instantiate_github_class,
    set_jobs_to_done,
    process_update_issue_status,
    process_create_issue,
    process_update_issue_body,
    close_issue_if_all_checked,
    process_update_progress,
    close_sub_tasks,
)
from src.models import IssueJob, Job, IssueJobStatus, JobStatus
from src.services import IssueJobService, JobService


@pytest.fixture(autouse=True)
def _get_auth():
    with patch("src.managers.issue_manager._get_auth") as mock:
        yield mock


@pytest.fixture(autouse=True)
def github():
    with patch("src.managers.issue_manager.github") as mock:
        yield mock


@pytest.fixture
def issue_helper(request):
    with patch("src.managers.issue_manager.issue_helper") as mock:
        yield mock


@pytest.mark.parametrize(
    "issue_job_service_output, issue_job_exists",
    [
        (False, False),
        (True, True),
    ],
)
def test_get_or_create_issue_job(
    issue_job_service_output, issue_job_exists, event, issue, issue_helper, issue_job
):
    if issue_job_exists:
        IssueJobService.insert_one(issue_job)
    # Now we can call the function and check its output
    result = get_or_create_issue_job(event)
    if issue_job_exists:
        assert result == IssueJobService.all()[0]
        issue_helper.update_issue_comment_status.assert_not_called()
    else:
        assert result == IssueJob(
            issue_url=issue_job.issue_url,
            repository_url="repository.url",
            title=event.issue.title,
            issue_comment_id=1,
            hook_installation_target_id=event.hook_installation_target_id,
            installation_id=event.installation_id,
            milestone_url="issue.milestone.url if issue.milestone else None",
        )
        issue_helper.update_issue_comment_status.assert_called_once()


@pytest.mark.parametrize(
    "event, handle_task_list_called, close_sub_tasks_called",
    [
        (IssueOpenedEvent, True, False),
        (IssueEditedEvent, True, False),
        (IssueClosedEvent, False, True),
        (None, False, False),  # Any other type of event
    ],
)
def test_manage(
    event,
    handle_task_list_called,
    close_sub_tasks_called,
):
    with (
        patch("src.managers.issue_manager.handle_task_list") as handle_task_list_mock,
        patch("src.managers.issue_manager.close_sub_tasks") as close_sub_tasks_mock,
    ):
        manage(Mock(spec=event))
        assert handle_task_list_mock.called == handle_task_list_called
        assert close_sub_tasks_mock.called == close_sub_tasks_called


@pytest.mark.parametrize(
    "tasks, existing_tasks, issue_job_status",
    [
        [
            [("task1", False), ("task2", False)],
            [],
            IssueJobStatus.PENDING,
        ],
        [
            [("task1", False), ("task2", False), ("task3", False)],
            [
                {"task": "task1", "checked": False},
                {"task": "task2", "checked": False},
            ],
            IssueJobStatus.RUNNING,
        ],
        [
            [("repo#1", True), ("repo#2", False), ("task3", False)],
            [
                {"task": "task1", "checked": False, "issue_ref": "repo#1"},
                {"task": "task2", "checked": False, "issue_ref": "repo#2"},
            ],
            IssueJobStatus.DONE,
        ],
        [
            [],
            [],
            None,
        ],
        [
            [("task1", False), ("task2", False)],
            [
                {"task": "task1", "checked": False},
                {"task": "task2", "checked": False},
            ],
            IssueJobStatus.RUNNING,
        ],
    ],
    ids=[
        "All new tasks",
        "Existing tasks and add new task",
        "Editing issue, with new task",
        "No task list",
        "No new task in task list",
    ],
)
def test_handle_task_list(
    event, issue, tasks, existing_tasks: list[dict], issue_job_status, issue_helper
):
    for existing_task in existing_tasks:
        JobService.insert_one(Job(original_issue_url=event.issue.url, **existing_task))

    issue_helper.get_tasklist.return_value = tasks
    issue_job = Mock(issue_job_status=issue_job_status)
    with patch(
        "src.managers.issue_manager.get_or_create_issue_job", return_value=issue_job
    ):
        result = handle_task_list(event)
        if tasks:
            assert result == issue_job
        else:
            assert result is None
        assert issue_job.issue_job_status != IssueJobStatus.DONE
    jobs = JobService.all()
    assert len(jobs) == len(tasks)
    for job, task in zip(jobs, tasks):
        assert (job.issue_ref or job.task) == task[0]
        assert job.original_issue_url == event.issue.url
        assert job.checked == task[1]
        assert job.job_status == JobStatus.PENDING


@pytest.mark.parametrize(
    "task, expected_url, expected_title, get_repository_return",
    [
        (
            "normal_text",
            "https://api.github.com/repos/heitorpolidoro/bartholomew-smith",
            "normal_text",
            None,
        ),
        (
            "other_repository",
            "other_repository.url",
            "title",
            Mock(url="other_repository.url"),
        ),
        (
            "[other_repository]",
            "https://api.github.com/repos/heitorpolidoro/other_repository",
            "title",
            Mock(url="other_repository.url"),
        ),
        (
            "[repo] task title",
            "https://api.github.com/repos/heitorpolidoro/repo",
            "task title",
            None,
        ),
        (
            "[owner/repo] task title",
            "https://api.github.com/repos/owner/repo",
            "task title",
            None,
        ),
    ],
    ids=[
        "normal_text",
        "just repository name",
        "just repository name using syntax",
        "repo with task title",
        "owner/repo with task title",
    ],
)
def test_get_title_and_repository_url(
    task, expected_url, expected_title, issue_job, get_repository_return, github
):
    with patch(
        "src.managers.issue_manager._get_repository", return_value=get_repository_return
    ):
        result_url, result_title = _get_title_and_repository_url(issue_job, task)
    assert result_url == expected_url
    assert result_title == expected_title


@pytest.mark.parametrize(
    "repository_name,expected_repository_name",
    [
        ("repo_name", "heitorpolidoro/repo_name"),
        ("owner/repo_name", "owner/repo_name"),
    ],
)
def test_get_repository(repository_name, expected_repository_name, issue_job):
    with patch("src.managers.issue_manager.get_repository") as get_repository_mock:
        _get_repository(issue_job, repository_name)
        get_repository_mock.assert_called_once_with(ANY, expected_repository_name)


def test_instantiate_github_class(_get_auth, github):
    clazz = Mock()

    with patch("src.managers.issue_manager.Requester") as requester:
        _instantiate_github_class(clazz, 1, 2, "url")
        requester.assert_called_once_with(
            auth=_get_auth.return_value,
            base_url=Consts.DEFAULT_BASE_URL,
            timeout=Consts.DEFAULT_TIMEOUT,
            user_agent=Consts.DEFAULT_USER_AGENT,
            per_page=Consts.DEFAULT_PER_PAGE,
            verify=True,
            retry=github.GithubRetry(),
            pool_size=None,
        )
        clazz.assert_called_once_with(
            requester=requester(),
            headers={},
            attributes={"url": "url"},
            completed=False,
        )


def test_set_jobs_to_done(issue_job):
    jobs = [
        Job(
            task="task1",
            original_issue_url=issue_job.issue_url,
            checked=False,
            job_issue=random.choice(list(JobStatus)),
        ),
    ]
    JobService.insert_many(jobs)
    with patch(
        "src.managers.issue_manager.process_update_progress"
    ) as process_update_progress_mock:
        set_jobs_to_done(jobs, issue_job)
        process_update_progress_mock.assert_called_once_with(issue_job)

    for job in JobService.all():
        assert job.job_status == JobStatus.DONE


@pytest.mark.parametrize(
    "issue_job_status,expected_return",
    [
        [None, None],
        [IssueJobStatus.PENDING, IssueJobStatus.DONE],
        [IssueJobStatus.RUNNING, IssueJobStatus.RUNNING],
    ],
    ids=[
        "No Issue Job",
        "With Issue Job pending",
        "With Issue Job running",
    ],
)
def test_process_jobs(issue_job_status, expected_return, issue_job):
    if issue_job_status:
        issue_job.issue_job_status = issue_job_status
        IssueJobService.insert_one(issue_job)

    with (
        patch("src.managers.issue_manager.process_update_issue_body"),
        patch("src.managers.issue_manager.process_pending_jobs"),
        patch("src.managers.issue_manager.process_update_issue_status"),
        patch("src.managers.issue_manager.process_create_issue"),
        patch("src.managers.issue_manager.close_issue_if_all_checked"),
        patch("src.managers.issue_manager.process_update_progress"),
    ):
        assert process_jobs(issue_job.issue_url) == expected_return
        if issue_job := next(iter(IssueJobService.all()), None):
            assert issue_job.issue_job_status == expected_return


@pytest.mark.parametrize(
    "task,expected_job_update_values,_get_repository_return",
    [
        (
            "task",
            {
                "job_status": JobStatus.CREATE_ISSUE,
                "title": "task",
                "repository_url": "https://api.github.com/repos/heitorpolidoro/bartholomew-smith",
            },
            None,
        ),
        (
            "owner/repo#1",
            {
                "job_status": JobStatus.UPDATE_ISSUE_STATUS,
                "issue_url": "https://api.github.com/repos/owner/repo/issues/1",
            },
            None,
        ),
        (
            "#1",
            {
                "job_status": JobStatus.UPDATE_ISSUE_STATUS,
                "issue_url": "https://api.github.com/repos/heitorpolidoro/bartholomew-smith/issues/1",
            },
            None,
        ),
    ],
    ids=[
        "Is not issue ref",
        "Is issue ref",
        "Is issue ref (just #num)",
    ],
)
def test_process_pending_jobs(
    task, expected_job_update_values, _get_repository_return, issue_job, github
):
    github.Github().get_repo.return_value = _get_repository_return

    JobService.insert_one(
        Job(original_issue_url=issue_job.issue_url, task=task, checked=False)
    )
    with patch(
        "src.managers.issue_manager._get_repository",
        return_value=_get_repository_return,
    ):
        process_pending_jobs(issue_job)

    job = JobService.all()[0]
    for k, v in expected_job_update_values.items():
        assert getattr(job, k) == v, f"Job.{k} should be {v}"


@pytest.mark.parametrize(
    "issue_state, checked, final_job_status",
    [
        ("open", True, JobStatus.DONE),
        ("open", False, JobStatus.DONE),
        ("closed", True, JobStatus.DONE),
        ("closed", False, JobStatus.DONE),
        ("open", True, JobStatus.ERROR),
    ],
)
def test_process_update_issue_status(issue_state, checked, issue_job, final_job_status):
    JobService.insert_one(
        Job(
            original_issue_url=issue_job.issue_url,
            task="task",
            checked=checked,
            job_status=JobStatus.UPDATE_ISSUE_STATUS,
        )
    )
    issue = Mock(state=issue_state)
    with (
        patch(
            "src.managers.issue_manager._instantiate_github_class", return_value=issue
        ),
    ):
        if final_job_status == JobStatus.ERROR:
            issue.edit.side_effect = UnknownObjectException(0)
        process_update_issue_status(issue_job)
        if issue_state == "open" and checked:
            issue.edit.assert_called_once_with(state="closed")
        elif issue_state == "closed" and not checked:
            issue.edit.assert_called_once_with(state="open")
        else:
            issue.edit.assert_not_called()
        job = JobService.all()[0]
        assert job.job_status == final_job_status


def test_process_create_issue(issue_job):
    JobService.insert_one(
        Job(
            original_issue_url=issue_job.issue_url,
            task="task",
            checked=False,
            job_status=JobStatus.CREATE_ISSUE,
            title="title",
        )
    )
    repository = Mock()
    with (
        patch(
            "src.managers.issue_manager._instantiate_github_class",
            return_value=repository,
        ),
    ):
        process_create_issue(issue_job)
        repository.create_issue.assert_called_once_with(title="title")
        job = JobService.all()[0]
        assert job.job_status == JobStatus.UPDATE_ISSUE_BODY


def test_process_update_issue_body(issue_job):
    JobService.insert_many(
        [
            Job(
                original_issue_url=issue_job.issue_url,
                task=f"task_{i}",
                checked=False,
                job_status=JobStatus.UPDATE_ISSUE_BODY,
                title="title",
            )
            for i in range(5)
        ]
    )
    issue = Mock(body="body")
    with (
        patch(
            "src.managers.issue_manager._instantiate_github_class",
            return_value=issue,
        ),
    ):
        process_update_issue_body(issue_job)
        for job in JobService.all():
            assert job.job_status == JobStatus.DONE
        issue.edit.assert_called_once()


@pytest.mark.parametrize(
    "tasks,should_close",
    [
        [[("task1", False), ("task2", False)], False],
        [[("task1", True), ("task2", True)], True],
        [[("task1", True), ("task2", False)], False],
    ],
    ids=[
        "All opened",
        "All closed",
        "1 closed",
    ],
)
def test_close_issue_if_all_checked(tasks, issue_job, issue_helper, should_close):
    issue = Mock()
    issue_helper.get_tasklist.return_value = tasks

    with (
        patch(
            "src.managers.issue_manager._instantiate_github_class",
            return_value=issue,
        ),
    ):
        close_issue_if_all_checked(issue_job)
        if should_close:
            issue.edit.assert_called_once_with(state="closed")
        else:
            issue.edit.assert_not_called()


@pytest.mark.parametrize(
    "issue_job_status", [IssueJobStatus.DONE, IssueJobStatus.RUNNING]
)
def test_process_update_progress(issue_job, issue_job_status, issue_helper):
    issue_job.issue_job_status = issue_job_status
    issue = Mock()

    with (
        patch(
            "src.managers.issue_manager._instantiate_github_class",
            return_value=issue,
        ),
    ):
        if issue_job_status == IssueJobStatus.DONE:
            process_update_progress(issue_job)
            issue_helper.update_issue_comment_status.assert_called_once_with(
                issue, "Job's done", issue_comment_id=issue_job.issue_comment_id
            )
        else:
            jobs = []
            done = 0
            for i in range(10):
                job_status = random.choice(list(JobStatus))
                if job_status == JobStatus.DONE:
                    done += 1
                jobs.append(
                    Job(
                        original_issue_url=issue_job.issue_url,
                        task=f"task_{i}",
                        checked=False,
                        job_status=job_status,
                        title="title",
                    )
                )
            JobService.insert_many(jobs)
            process_update_progress(issue_job)
            total = len(jobs)
            issue_helper.update_issue_comment_status.assert_called_once_with(
                issue,
                f"Analyzing the tasklist [{done}/{total}]\n{markdown_progress(done, total)}",
                issue_comment_id=issue_job.issue_comment_id,
            )


def test_close_sub_tasks(event, issue_helper):
    tasks = [
        ("not ref", False),
        ("owner/repo#1", False),
        ("#2", False),
        ("#0", False),
        ("owner/error#3", False),
    ]
    issue_helper.get_tasklist.return_value = tasks
    event.repository = Mock(url="repository.url")
    issues = []

    def instantiate_github_class_mock(_clazz, _hook_id, _installlation_id, issue_url):
        issue_ = Mock()
        issues.append(issue_)
        if issue_url.endswith("0"):
            issue_.state = "closed"
        elif issue_url.endswith("3"):
            issue_.edit.side_effect = UnknownObjectException(0)
        return issue_

    with patch(
        "src.managers.issue_manager._instantiate_github_class",
        side_effect=instantiate_github_class_mock,
    ) as mock_instantiate_github_class:
        close_sub_tasks(event)
        mock_instantiate_github_class.assert_has_calls(
            [
                call(ANY, ANY, ANY, "https://api.github.com/repos/owner/repo/issues/1"),
                call(ANY, ANY, ANY, "repository.url/issues/2"),
                call(ANY, ANY, ANY, "repository.url/issues/0"),
                call(ANY, ANY, ANY, "https://api.github.com/repos/owner/error/issues/3"),
            ]
        )
        for issue in issues:
            if issue.state == "closed":
                issue.edit.assert_not_called()
            else:
                issue.edit.assert_called_once_with(
                    state="closed", state_reason=event.issue.state_reason
                )
