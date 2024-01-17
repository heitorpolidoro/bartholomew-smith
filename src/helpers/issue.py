import re


def get_tasklist(issue_body: str) -> list[tuple[bool, str]]:
    tasks = []
    for line in issue_body.split("\n"):
        if task := re.match(r"- \[(.)] (.*)", line):
            tasks.append((task.group(1) == "x", task.group(2)))
    return tasks


def issue_ref(created_issue):
    return f"{created_issue.repository.full_name}#{created_issue.number}"
