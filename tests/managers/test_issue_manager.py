from collections import defaultdict
from unittest.mock import ANY, Mock, patch

import pytest

from src.managers.issue_manager import (
    parse_issue_and_create_jobs,
    process_create_issue,
    process_jobs,
    process_pending_jobs,
    process_update_issue_body,
    process_update_issue_status,
)
from src.models import IssueJob, IssueJobStatus, Job, JobStatus
from src.services import IssueJobService, JobService


@pytest.fixture(autouse=True)
def get_repository_mock(repo_batata, repository):
    def mocked_get_repository(_gh, repository_name, _owner=None):
        return {
            "heitorpolidoro/repo_batata": repo_batata,
            "heitorpolidoro/bartholomew-smith": repository,
        }.get(repository_name, None)

    with (
        patch(
            "src.managers.issue_manager.get_repository",
            side_effect=mocked_get_repository,
        ) as mock,
        patch(
            "src.helpers.issue_helper.get_repository",
            side_effect=mocked_get_repository,
        ),
    ):
        yield mock


@pytest.fixture
def repo_batata(created_issue):
    """
    This fixture returns a mock repository object with default values for the attributes.
    :return: Mocked Repository
    """
    repository = Mock(
        full_name="heitorpolidoro/repo_batata",
        owner=Mock(login="heitorpolidoro"),
        url="https://api.github.com/repos/heitorpolidoro/repo_batata",
    )
    repository.create_issue.return_value = created_issue
    return repository


@pytest.fixture
def created_issue(repository):
    created_issue = Mock(repository=repository)
    repository.create_issue.return_value = created_issue
    yield created_issue


@pytest.fixture
def issue_helper_mock(issue_comment, issue, repository):
    with patch("src.managers.issue_manager.issue_helper") as issue_helper:
        from src.helpers.issue_helper import get_tasklist

        issue_helper.get_tasklist = get_tasklist
        issue_helper.update_issue_comment_status.return_value = issue_comment
        issue_helper.get_issue = lambda _, _2, task: issue if "#" in task else None
        yield issue_helper


@pytest.fixture
def issue_job():
    return IssueJob(
        issue_url="https://api.github.com/repos/heitorpolidoro/bartholomew-smith/issues/1",
        repository_url="https://api.github.com/repos/heitorpolidoro/bartholomew-smith",
        title="Issue Title",
        issue_job_status=IssueJobStatus.PENDING,
        issue_comment_id=2,
        hook_installation_target_id=3,
        installation_id=4,
    )


def test_parse_issue_and_create_jobs_when_no_task_list(issue, issue_helper_mock):
    parse_issue_and_create_jobs(issue, 123, 321)
    issue_helper_mock.update_issue_comment_status.assert_called_once()
    assert JobService.all() == []


def test_parse_issue_and_create_jobs_when_has_task_list(issue, issue_helper_mock):
    issue.body = """- [ ] batata1
- [x] batata2
- [ ] batata3
- [ ] heitorpolidoro/bartholomew-smith#321
- [x] heitorpolidoro/bartholomew-smith#123
"""
    parse_issue_and_create_jobs(issue, 123, 321)
    issue_helper_mock.update_issue_comment_status.assert_called_once()

    issue_jobs = IssueJobService.all()
    assert len(issue_jobs) == 1
    created_issue_job = issue_jobs[0]
    assert (
        created_issue_job.issue_url
        == "https://api.github.com/repos/heitorpolidoro/bartholomew-smith/issues/1"
    )
    assert (
        created_issue_job.repository_url
        == "https://api.github.com/repos/heitorpolidoro/bartholomew-smith"
    )

    jobs = JobService.all()
    assert len(jobs) == 5

    checks = defaultdict(int)
    status_set = set()
    issue_url_set = set()
    for t in jobs:
        status_set.add(t.job_status)
        checks[t.checked] += 1
        issue_url_set.add(t.original_issue_url)
    assert status_set == {JobStatus.PENDING}
    assert issue_url_set == {
        "https://api.github.com/repos/heitorpolidoro/bartholomew-smith/issues/1"
    }
    assert checks[True] == 2
    assert checks[False] == 3


def test_parse_issue_and_create_jobs_when_issue_job_already_exists(
    issue, issue_helper_mock, issue_job
):
    IssueJobService.insert_one(issue_job)
    issue.body = """- [ ] heitorpolidoro/bartholomew-smith#111
- [x] batata2
- [ ] batata3
- [ ] heitorpolidoro/bartholomew-smith#321
- [x] heitorpolidoro/bartholomew-smith#123
- [ ] batata4
"""
    JobService.insert_many(
        [
            Job(
                task="batata1",
                original_issue_url=issue_job.issue_url,
                checked=False,
                issue_ref="heitorpolidoro/bartholomew-smith#111",
            ),
            Job(
                task="heitorpolidoro/bartholomew-smith#321",
                original_issue_url=issue_job.issue_url,
                checked=False,
                issue_url="issue_url",
            ),
        ]
    )
    parse_issue_and_create_jobs(issue, 123, 321)
    issue_helper_mock.update_issue_comment_status.assert_not_called()

    issue_jobs = IssueJobService.all()
    assert len(issue_jobs) == 1
    created_issue_job = issue_jobs[0]
    assert (
        created_issue_job.issue_url
        == "https://api.github.com/repos/heitorpolidoro/bartholomew-smith/issues/1"
    )
    assert (
        created_issue_job.repository_url
        == "https://api.github.com/repos/heitorpolidoro/bartholomew-smith"
    )

    jobs = JobService.all()
    assert len(jobs) == 6

    checks = defaultdict(int)
    status_set = set()
    issue_url_set = set()
    for t in jobs:
        status_set.add(t.job_status)
        checks[t.checked] += 1
        issue_url_set.add(t.original_issue_url)
    assert status_set == {JobStatus.PENDING}
    assert issue_url_set == {
        "https://api.github.com/repos/heitorpolidoro/bartholomew-smith/issues/1"
    }
    assert checks[True] == 2
    assert checks[False] == 4


def test_process_jobs(issue_job):
    job = Job(
        task="Task Title",
        original_issue_url=issue_job.issue_url,
        checked=False,
    )
    JobService.insert_one(job)
    IssueJobService.insert_one(issue_job)
    with (
        patch("src.managers.issue_manager.Repository") as repository_mock,
        patch("src.managers.issue_manager.Issue") as issue_mock,
    ):
        repository = Mock(full_name="repo")
        repository_mock.return_value = repository
        repository.create_issue.return_value = Mock(repository=repository, number=1)

        issue = Mock(body="- [ ] Task Title")
        issue_mock.return_value = issue

        process_jobs(issue_job.issue_url)

        repository_mock.assert_called_once_with(
            requester=ANY,
            headers={},
            attributes={"url": issue_job.repository_url},
            completed=False,
        )
        repository.create_issue.assert_called_once_with(title="Task Title")

        issue.edit.assert_called_once_with(body="- [ ] repo#1")

    changed_job = JobService.filter(
        task=job.task, original_issue_url=job.original_issue_url
    )[0]
    assert changed_job.job_status == JobStatus.DONE
    assert changed_job.title == "Task Title"
    assert (
        changed_job.repository_url
        == "https://api.github.com/repos/heitorpolidoro/bartholomew-smith"
    )

    changed_issue_job = IssueJobService.filter(issue_url=issue_job.issue_url)[0]
    assert changed_issue_job.issue_job_status == IssueJobStatus.DONE


def test_process_jobs_when_not_pending(issue_job):
    issue_job.issue_job_status = IssueJobStatus.DONE
    IssueJobService.insert_one(issue_job)
    with (
        patch("src.managers.issue_manager.Repository") as repository_mock,
        patch("src.managers.issue_manager.Issue") as issue_mock,
    ):
        repository = Mock()
        repository_mock.return_value = repository
        repository.create_issue.return_value = Mock(url="issue_url")

        issue = Mock(body="- [ ] Task Title")
        issue_mock.return_value = issue

        process_jobs(issue_job.issue_url)

        repository_mock.assert_not_called()
        repository.create_issue.assert_not_called()

        issue.edit.assert_not_called()

    changed_issue_job = IssueJobService.filter(issue_url=issue_job.issue_url)[0]
    assert changed_issue_job.issue_job_status == IssueJobStatus.DONE


def test_process_jobs_when_dont_exist():
    with (
        patch("src.managers.issue_manager.Repository") as repository_mock,
        patch("src.managers.issue_manager.Issue") as issue_mock,
    ):
        repository = Mock()
        repository_mock.return_value = repository
        repository.create_issue.return_value = Mock(url="issue_url")

        issue = Mock(body="- [ ] Task Title")
        issue_mock.return_value = issue

        process_jobs("issue_job.issue_url")

        repository_mock.assert_not_called()
        repository.create_issue.assert_not_called()

        issue.edit.assert_not_called()

    assert IssueJobService.all() == []


@pytest.mark.parametrize(
    "job_params,expected_changes",
    [
        (
            {"task": "#123"},
            {
                "job_status": JobStatus.UPDATE_ISSUE_STATUS,
                "issue_url": "https://api.github.com/repos/heitorpolidoro/bartholomew-smith/issues/123",
            },
        ),
        (
            {"task": "heitorpolidoro/repo_batata#123"},
            {
                "job_status": JobStatus.UPDATE_ISSUE_STATUS,
                "issue_url": "https://api.github.com/repos/heitorpolidoro/repo_batata/issues/123",
            },
        ),
        (
            {"task": "[heitorpolidoro/repo_batata]"},
            {
                "job_status": JobStatus.CREATE_ISSUE,
                "repository_url": "https://api.github.com/repos/heitorpolidoro/repo_batata",
                "title": "Issue Title",
            },
        ),
        (
            {"task": "[heitorpolidoro/repo_batata] title"},
            {
                "job_status": JobStatus.CREATE_ISSUE,
                "repository_url": "https://api.github.com/repos/heitorpolidoro/repo_batata",
                "title": "title",
            },
        ),
        (
            {"task": "[repo_batata] title2"},
            {
                "job_status": JobStatus.CREATE_ISSUE,
                "repository_url": "https://api.github.com/repos/heitorpolidoro/repo_batata",
                "title": "title2",
            },
        ),
        (
            {"task": "repo_batata"},
            {
                "job_status": JobStatus.CREATE_ISSUE,
                "repository_url": "https://api.github.com/repos/heitorpolidoro/repo_batata",
                "title": "Issue Title",
            },
        ),
        (
            {"task": "heitorpolidoro/repo_batata"},
            {
                "job_status": JobStatus.CREATE_ISSUE,
                "repository_url": "https://api.github.com/repos/heitorpolidoro/repo_batata",
                "title": "Issue Title",
            },
        ),
        (
            {"task": "just the title"},
            {
                "job_status": JobStatus.CREATE_ISSUE,
                "repository_url": "https://api.github.com/repos/heitorpolidoro/bartholomew-smith",
                "title": "just the title",
            },
        ),
        (
            {"task": "title3"},
            {
                "job_status": JobStatus.CREATE_ISSUE,
                "repository_url": "https://api.github.com/repos/heitorpolidoro/bartholomew-smith",
                "title": "title3",
            },
        ),
    ],
)
def test_process_pending_jobs(issue_job, job_params, expected_changes):
    job_params.update(**{"original_issue_url": issue_job.issue_url, "checked": False})
    job = Job(**job_params)
    JobService.insert_one(job)
    process_pending_jobs(issue_job)
    changed_job = JobService.filter(
        task=job.task, original_issue_url=job.original_issue_url
    )[0]
    for key, value in changed_job.model_dump().items():
        value_to_assert = expected_changes.get(key) or getattr(job, key)
        assert value == value_to_assert, f"{key} in {job.task}"


@pytest.mark.parametrize(
    "checked,issue_state,call_edit",
    [
        (False, "open", False),
        (False, "closed", True),
        (True, "open", True),
        (True, "closed", False),
    ],
)
def test_process_update_issue_status(issue_job, checked, issue_state, call_edit):
    job = Job(
        task="#123",
        original_issue_url=issue_job.issue_url,
        job_status=JobStatus.UPDATE_ISSUE_STATUS,
        checked=checked,
    )
    JobService.insert_one(job)
    with patch("src.managers.issue_manager.Issue") as issue_mock:
        issue = Mock(state=issue_state)
        issue_mock.return_value = issue
        process_update_issue_status(issue_job)
        if call_edit:
            issue.edit.assert_called_once()
        else:
            issue.edit.assert_not_called()
    changed_job = JobService.filter(
        task=job.task, original_issue_url=job.original_issue_url
    )[0]
    assert changed_job.job_status == JobStatus.DONE


def test_process_create_issue(issue_job):
    job = Job(
        task="#123",
        original_issue_url=issue_job.issue_url,
        job_status=JobStatus.CREATE_ISSUE,
        repository_url="repository_url",
        checked=False,
        title="Test Title",
    )
    JobService.insert_one(job)
    with patch("src.managers.issue_manager.Repository") as repository_mock:
        repository = Mock(full_name="repo")
        repository_mock.return_value = repository
        repository.create_issue.return_value = Mock(repository=repository, number=1)

        process_create_issue(issue_job)

        repository_mock.assert_called_once_with(
            requester=ANY,
            headers={},
            attributes={"url": "repository_url"},
            completed=False,
        )
        repository.create_issue.assert_called_once_with(title="Test Title")
    changed_job = JobService.filter(
        task=job.task, original_issue_url=job.original_issue_url
    )[0]
    assert changed_job.job_status == JobStatus.UPDATE_ISSUE_BODY
    assert changed_job.issue_ref == "repo#1"


def test_process_update_issue_body(issue_job):
    jobs = [
        Job(
            task="123",
            original_issue_url=issue_job.issue_url,
            checked=False,
            job_status=JobStatus.UPDATE_ISSUE_BODY,
            issue_ref="repo#123",
        ),
        Job(
            task="321",
            original_issue_url=issue_job.issue_url,
            checked=False,
            job_status=JobStatus.UPDATE_ISSUE_BODY,
            issue_ref="repo#321",
        ),
    ]
    JobService.insert_many(jobs)
    with patch("src.managers.issue_manager.Issue") as issue_mock:
        issue = Mock(
            body="""- [ ] 123
- [ ] 1123
- [ ] 3211
- [ ] 321"""
        )
        issue_mock.return_value = issue
        process_update_issue_body(issue_job)
        issue.edit.assert_called_once_with(
            body="""- [ ] repo#123
- [ ] 1123
- [ ] 3211
- [ ] repo#321"""
        )
    for changed_job in JobService.filter(original_issue_url=issue_job.issue_url):
        assert changed_job.job_status == JobStatus.DONE, changed_job.task
