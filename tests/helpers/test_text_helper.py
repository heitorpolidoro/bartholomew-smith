import pytest

from src.helpers import text_helper


@pytest.mark.parametrize(
    "count, total, expected_result",
    [
        (
            0,
            5,
            "![](https://geps.dev/progress/0?dangerColor=006600&warningColor=006600&successColor=006600)",
        ),
        (
            5,
            5,
            "![](https://geps.dev/progress/100?dangerColor=006600&warningColor=006600&successColor=006600)",
        ),
    ],
)
def test_markdown_progress(count, total, expected_result):
    assert text_helper.markdown_progress(count, total) == expected_result


@pytest.mark.parametrize(
    "task, expected_result",
    [
        ("owner/repo#123", True),
        ("test_task", False),
    ],
)
def test_is_issue_ref(task, expected_result):
    assert text_helper.is_issue_ref(task) == expected_result


@pytest.mark.parametrize(
    "task, expected_result",
    [
        ("[repo] test_task", ("repo", "test_task")),
        ("test task with no brackets", None),
    ],
)
def test_extract_repo_title(task, expected_result):
    assert text_helper.extract_repo_title(task) == expected_result
