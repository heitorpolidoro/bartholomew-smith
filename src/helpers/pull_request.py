import logging
import re
from string import Template
from typing import Optional

from github import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository

logger = logging.getLogger(__name__)

BODY_ISSUE_TEMPLATE = """### [$title](https://github.com/$repo_full_name/issues/$issue_num)

$body

Closes #$issue_num

"""


def get_existing_pull_request(
    repository: Repository, head: str
) -> Optional[PullRequest]:
    """
    Returns an existing PR if it exists.
    :param repository: The Repository to get the PR from.
    :param head: The branch to check for an existing PR.
    :return: Exists PR or None.
    """
    return next(iter(repository.get_pulls(state="open", head=head)), None)


def create_pull_request(repository: Repository, branch: str) -> Optional[PullRequest]:
    """
    Creates a PR from the default branch to the given branch.

    If the branch name match a issue-9999 pattern, the title and the body of the PR will be generated using
    the information from the issue
    :param repository: The Repository to create the PR in.
    :param branch:
    :return: Created PR or None.
    :raises: GithubException if and error occurs, except if the error is "No commits between 'master' and 'branch'"
    in that case ignores the exception and it returns None.
    """
    try:
        title = ""
        body = ""
        for issue_num in re.findall(r"issue-(\d+)", branch, re.IGNORECASE):
            issue = repository.get_issue(int(issue_num))
            title = title or issue.title.strip()
            body += Template(BODY_ISSUE_TEMPLATE).substitute(
                title=issue.title,
                repo_full_name=repository.full_name,
                issue_num=issue_num,
                body=issue.body or "",
            )
        pr = repository.create_pull(
            repository.default_branch,
            branch,
            title=title or branch,
            body=body or "Pull Request automatically created",
            draft=False,
        )
        return pr
    except GithubException as ghe:
        if ghe.data and any(
            error["message"]
            == f"No commits between {repository.default_branch} and {branch}"
            for error in ghe.data["errors"]
        ):
            logger.warning(
                "No commits between '%s' and '%s'", repository.default_branch, branch
            )
        else:
            raise
    return None


def get_or_create_pull_request(
    repository: Repository, branch: str
) -> Optional[PullRequest]:
    """
    Get a existing PR or create a new one if none exists
    :param repository:
    :param branch:
    :return: The created or recovered PR or None if no commits between 'master' and 'branch'
    """
    if pr := get_existing_pull_request(
        repository, f"{repository.owner.login}:{branch}"
    ):
        print(
            f"PR already exists for '{repository.owner.login}:{branch}' into "
            f"'{repository.default_branch} (PR#{pr.number})'"
        )
        logger.info(
            "PR already exists for '%s:%s' into '%s'",
            repository.owner.login,
            branch,
            repository.default_branch,
        )
    else:
        pr = create_pull_request(repository, branch)
    return pr

