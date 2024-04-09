import logging
from typing import Optional

from github import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository

logger = logging.getLogger(__name__)


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


def create_pull_request(
    repository: Repository, branch: str, title: str, body: str
) -> Optional[PullRequest]:
    """
    Creates a PR from the default branch to the given branch.

    If the branch name match an issue-9999 pattern, the title and the body of the PR will be generated using
    the information from the issue
    :param repository: The Repository to create the PR in.
    :param branch: The head branch to create the Pull Request
    :param title: The title of the Pull Request
    :param body: The body of the Pull Request
    :return: Created PR or None.
    :raises: GithubException if and error occurs, except if the error is "No commits between 'master' and 'branch'"
    in that case ignores the exception, and it returns None.
    """
    try:
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
