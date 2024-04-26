import pytest

from unittest.mock import MagicMock, patch
from src.helpers import request_helper


@pytest.mark.parametrize(
    "request_url, issue_url",
    [
        ("http://example.com", "http://issue.com/1"),  # test with some URL
        ("", ""),  # test with empty strings
    ],
)
def test_make_thread_request(request_url, issue_url):
    with patch("threading.Thread") as MockThread:
        request_helper.make_thread_request(request_url, issue_url)
        MockThread.assert_called_once_with(
            target=request_helper.make_request, args=(request_url, issue_url)
        )


@pytest.mark.parametrize(
    "request_url, issue_url",
    [
        ("http://example.com", "http://issue.com/1"),  # test with some URL
        ("", ""),  # test with empty strings
    ],
)
def test_make_request(request_url, issue_url):
    with patch("requests.post") as MockPost:
        request_helper.make_request(request_url, issue_url)
        MockPost.assert_called_once_with(request_url, json={"issue_url": issue_url})


@pytest.mark.parametrize(
    "endpoint, expected_request_url",
    [
        ("test_endpoint", "http://base.com/test_endpoint"),  # test with some endpoint
        ("", "http://base.com/"),  # test with empty string
    ],
)
def test_get_request_url(endpoint, expected_request_url):
    with patch("src.helpers.request_helper.flask") as MockFlask:
        MockFlask.request.base_url = "http://base.com/"
        MockFlask.url_for.return_value = endpoint
        assert request_helper.get_request_url(endpoint) == expected_request_url
