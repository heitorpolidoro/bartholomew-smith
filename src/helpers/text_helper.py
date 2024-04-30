"""General Methods for text"""

from typing import Any, Optional, Union


def markdown_progress(count: int, total: int) -> str:
    """Returns a markdown progress"""
    return (
        f"![](https://geps.dev/progress/{int(count/total*100)}"
        "?dangerColor=006600&warningColor=006600&successColor=006600)"
    )


def is_issue_ref(text: str) -> bool:
    """Returns if the text is an issue reference owner/repository#123"""
    split = text.split("#")
    if len(split) != 2:
        return False

    repository, issue_num = split
    if not issue_num.isdigit() or repository and repository.count("/") != 1:
        return False
    else:
        return True


def extract_repo_title(text: str) -> Optional[tuple[Union[str, Any], ...]]:
    """Returns if the text is in a repository-title format"""
    text = text.strip()
    parts = text.split("]")
    if len(parts) > 1 and parts[0][0] == "[":
        key = parts[0][1:].strip()
        value = parts[1].strip()
        return key, value
    return None
