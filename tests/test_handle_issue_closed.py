from app import handle_issue_closed


def test_handle_issue_closed(event, issue, handle_close_tasklist_mock):
    handle_issue_closed(event)
    handle_close_tasklist_mock.assert_called_once_with(event)


def test_handle_issue_closed_when_issue_has_no_body(
    event, issue, handle_close_tasklist_mock
):
    issue.body = None
    handle_issue_closed(event)
    handle_close_tasklist_mock.assert_not_called()
