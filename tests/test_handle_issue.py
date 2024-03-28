import json

from githubapp import Config

from app import handle_issue

# def test_handle_issue_opened_or_edited(event, parse_issue_and_create_jobs_mock):
#     handle_issue(event)
#     parse_issue_and_create_jobs_mock.assert_called_once_with(
#         event.issue, event.hook_installation_target_id, event.installation_id
#     )


def test_handle_issue_opened_or_edited_when_issue_has_no_body(
    event, issue, parse_issue_and_create_jobs_mock
):
    issue.body = None
    handle_issue(event)
    parse_issue_and_create_jobs_mock.assert_not_called()


# def test_handle_issue_full_workflow(event, issue, sqs_mock):
#     issue.body = """
# - [ ] task1
# - [x] task2
# - [ ] repo#3
# - [x] repo#4
# """
#     handle_issue(event)
#     messages = sqs_mock.messages[Config.task_queue]
#     message = json.loads(messages[0])
#     assert message["context"] == {
#         "issue": "heitorpolidoro/bartholomew-smith#123",
#         "tasks": [
#             ["task1", False],
#             ["task2", True],
#             ["repo#3", False],
#             ["repo#4", True],
#         ],
#         "total": 4,
#     }
#
#     handle_tasklist_step(**message)
