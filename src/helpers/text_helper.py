import re


def markdown_progress(count, total):
    return (
        f"![](https://geps.dev/progress/{int(count/total*100)}"
        "?dangerColor=006600&warningColor=006600&successColor=006600)"
    )


def is_issue_ref(task):
    return bool(re.match(r"(.*/.*)?#\d+", task))


def is_repo_title_syntax(task):
    return bool(extract_repo_title(task))


def extract_repo_title(task):
    if match := re.match(r"\[(.+)] *(.*)", task):
        return match.groups()
    return None
