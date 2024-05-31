from unittest.mock import Mock

import pytest


@pytest.fixture
def check_run():
    yield Mock()


@pytest.fixture
def event(issue, repository_mock, check_run):
    check_suite = Mock(head_branch="master")
    event = Mock(
        hook_installation_target_id=1,
        installation_id=1,
        issue=issue,
        repository=repository_mock,
        check_suite=check_suite,
    )
    event.start_check_run.return_value = check_run
    return event


@pytest.fixture
def issue(repository_mock):
    return Mock(
        repository=repository_mock,
        number=123,
        url="issue.url",
        title="Test issue",
    )


@pytest.fixture
def pull_request():
    return Mock(number=123)


@pytest.fixture
def gh():
    return Mock()


# @pytest.fixture
# def issue_job():
#     return IssueJob(
#         issue_job_status=IssueJobStatus.PENDING,
#         issue_url="issue.url",
#         repository_url="https://api.github.com/repos/heitorpolidoro/bartholomew-smith",
#         title="title",
#         issue_comment_id=1,
#         hook_installation_target_id=1,
#         installation_id=1,
#     )
#
#
# @pytest.fixture(autouse=True)
# def fixed_datetime_now():
#     with patch("src.helpers.db_helper.datetime") as mock:
#         mock.now.return_value = datetime.datetime(2022, 4, 1, 0, 0)
#         yield mock.now
#
#
# @pytest.fixture(autouse=True)
# def base_model_service_stub():
#     class TableStub(MagicMock):
#         def __init__(self, *args: Any, **kw: Any):
#             super().__init__(*args, **kw)
#             self.table_name = args[0]
#             self.creation_date_time = 385959600.0
#             self.items = []
#
#         def scan(self, *args, ExpressionAttributeValues=None, **kwargs):
#             ExpressionAttributeValues = ExpressionAttributeValues or {}
#             items = []
#             for item in self.items:
#                 if all(
#                     item.get(k[1:]) == v for k, v in ExpressionAttributeValues.items()
#                 ):
#                     items.append(item)
#
#             return {"Items": items}
#
#         def put_item(self, Item):
#             self.items.append(Item)
#
#         def update_item(self, Key, ExpressionAttributeValues, **kw):
#             for item in self.items:
#                 if all(item.get(k) == v for k, v in Key.items()):
#                     item.update(
#                         {k[1:]: v for k, v in ExpressionAttributeValues.items()}
#                     )
#                     return
#
#         @contextmanager
#         def batch_writer(self):
#             yield self
#
#     class BaseModelServiceStub(BaseModelService):
#         resource = Mock(Table=TableStub)
#
#     with (
#         patch(
#             "src.helpers.db_helper.BaseModelService", new_callable=BaseModelServiceStub
#         ) as base_model_service_stub,
#     ):
#         yield base_model_service_stub
#         for sub_service in BaseModelService.__subclasses__():
#             sub_service._table = None
