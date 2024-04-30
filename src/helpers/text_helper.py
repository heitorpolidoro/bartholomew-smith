"""General Methods for text"""

import re
from typing import Any, Optional, Union


def markdown_progress(count: int, total: int) -> str:
    """Returns a markdown progress"""
    return (
        f"![](https://geps.dev/progress/{int(count/total*100)}"
        "?dangerColor=006600&warningColor=006600&successColor=006600)"
    )


def is_issue_ref(text: str) -> bool:
    """Returns if the text is an issue reference owner/repository#123"""
    return bool(re.match(r"(.*/.*)?#\d+", text))


def extract_repo_title(text: str) -> Optional[tuple[Union[str, Any], ...]]:
    """Returns if the text is in a repository-title format"""
    if match := re.match(r"\[(.+)] *(.*)", text):
        return match.groups()
    return None
