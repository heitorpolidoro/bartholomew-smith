# from unittest import TestCase
# from unittest.mock import Mock, patch
#
# import pytest
#
# from app import (
#     app,
#     handle_check_suite_completed,
#     handle_check_suite_requested,
#     handle_issue,
# )
# from src.models import IssueJob, IssueJobStatus
#
#
# @pytest.fixture
# def pull_request_manager():
#     with patch("app.pull_request_manager") as mock:
#         yield mock
#
#
# @pytest.fixture
# def release_manager():
#     with patch("app.release_manager") as mock:
#         yield mock
#
#
# @pytest.fixture
# def issue_manager():
#     with patch("app.issue_manager") as mock:
#         yield mock
#
#
# @pytest.fixture
# def request_helper(request):
#     with patch("app.request_helper") as mock:
#         if request.cls:
#             request.cls.request_helper = mock
#         yield mock
#
#
# @pytest.fixture
# def issue_job_service(request):
#     with patch("app.IssueJobService") as mock:
#         if request.cls:
#             request.cls.issue_job_service = mock
#         yield mock
#
#
# @pytest.fixture(autouse=True)
# def process():
#     with patch("app.Process") as mock:
#         mock().is_alive.return_value = False
#         yield mock
#
#
# def test_handle_check_suite_completed(event, pull_request_manager):
#     handle_check_suite_completed(event)
#     pull_request_manager.auto_update_pull_requests.assert_called_once_with(event)
#
#
# def test_handle_issue(event, issue_manager, issue_job_service):
#     issue_manager.manage.return_value = Mock(issue_url="issue_url")
#     with patch("app.process_jobs_endpoint") as process_jobs_endpoint_mock:
#         handle_issue(event)
#         issue_manager.manage.assert_called_once_with(event)
#         process_jobs_endpoint_mock.assert_called_once_with("issue_url")
#
#
# def test_handle_issue_when_issue_manager_returns_none(
#     event, issue_manager, issue_job_service
# ):
#     issue_manager.manage.return_value = None
#     with patch("app.process_jobs_endpoint") as process_jobs_endpoint_mock:
#         handle_issue(event)
#         issue_manager.manage.assert_called_once_with(event)
#         process_jobs_endpoint_mock.assert_not_called()
#
#
# def test_handle_issue_job_running(event, issue_manager, request_helper):
#     issue_manager.manage.return_value = Mock(
#         issue_url="issue_url", issue_job_status=IssueJobStatus.RUNNING
#     )
#     handle_issue(event)
#     issue_manager.manage.assert_called_once_with(event)
#     request_helper.make_thread_request.assert_not_called()
#
#
# @pytest.mark.usefixtures("request_helper", "issue_job_service")
# class TestApp(TestCase):
#     def setUp(self):
#         self.client = app.test_client()
#         self.patches = []
#         for p in self.patches:
#             p.start()
#
#     def tearDown(self):
#         for p in self.patches:
#             p.stop()
#
#     def test_process_jobs(self):
#         self.issue_job_service.filter.return_value = [
#             Mock(spec=IssueJob, issue_job_status=IssueJobStatus.RUNNING)
#         ]
#         with patch("app.Process") as process:
#             process.return_value.is_alive.return_value = False
#             response = self.client.post(
#                 "/process_jobs", json={"issue_url": "issue_url"}
#             )
#             assert response.status_code == 200
#             assert response.json["status"] == "running"
#
#             from src.managers import issue_manager
#
#             process.assert_called_once_with(
#                 target=issue_manager.process_jobs, args=("issue_url",)
#             )
#             self.request_helper.make_thread_request.assert_not_called()
#
#     @patch("app.IssueJobService")
#     def test_process_jobs_process_alive(self, issue_job_service):
#         issue_job = Mock(spec=IssueJob, issue_job_status=IssueJobStatus.PENDING)
#         issue_job_service.filter.return_value = [issue_job]
#         self.request_helper.get_request_url.return_value = "request.url"
#         with patch("app.Process") as process:
#             process.return_value.is_alive.return_value = True
#
#             response = self.client.post(
#                 "/process_jobs", json={"issue_url": "issue_url"}
#             )
#             assert response.status_code == 200
#             assert response.json["status"] == "pending"
#             issue_job_service.update.assert_called_once_with(
#                 issue_job, issue_job_status=IssueJobStatus.PENDING
#             )
#
#             self.request_helper.make_thread_request.assert_called_once_with(
#                 "request.url", "issue_url"
#             )
#
#     def test_process_jobs_issue_url_not_found(self):
#         response = self.client.post("/process_jobs", json={"issue_url": "not found"})
#         assert response.status_code == 404
#         assert response.json["error"] == "IssueJob for issue_url='not found' not found"
#
#     def test_process_jobs_without_issue_url(self):
#         response = self.client.post("/process_jobs", json={})
#         assert response.status_code == 400
#         assert response.json["error"] == "issue_url is required"
