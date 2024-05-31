"""Method to helps with Github PullRequests"""

import logging
from typing import NoReturn, Optional, Union

import github
from cachetools import Cache
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config

from src.helpers import repository_helper

logger = logging.getLogger(__name__)
cache = Cache(10)


def get_existing_pull_request(
    repository: Repository, branch: str
) -> Optional[PullRequest]:
    """
    Returns an existing PR if it exists.
    :param repository: The Repository to get the PR from.
    :param branch: The branch to check for an existing PR.
    :return: Exists PR or None.
    """
    key = f"{repository.owner.login}:{branch}"
    if pull_request := cache.get(key):
        return pull_request
    return next(iter(repository.get_pulls(state="open", head=key)), None)


def create_pull_request(
    repository: Repository, branch: str, title: str = None, body: str = None
) -> None:
    """
    Create a pull request in the given repository.

    :param repository: The repository object where the pull request will be created.
    :type repository: Repository
    :param branch: The name of the branch for the pull request.
    :type branch: str
    :param title: The title of the pull request. If not provided, the branch name will be used.
    :type title: str, optional
    :param body: The description or body of the pull request. If not provided, a default message will be used.
    :type body: str, optional
    :return: None
    """
    pull_request = repository.create_pull(
        repository.default_branch,
        branch,
        title=title or branch,
        body=body or "Pull Request automatically created",
        draft=False,
    )
    cache[f"{repository.owner.login}:{branch}"] = pull_request


def update_pull_requests(repository: Repository, base_branch: str) -> list[PullRequest]:
    """Updates all the pull requests in the given branch if is updatable."""
    updated_pull_requests = []
    for pull_request in repository.get_pulls(state="open", base=base_branch):
        if pull_request.mergeable_state == "behind":
            if pull_request.update_branch():
                updated_pull_requests.append(pull_request)
    return updated_pull_requests


def approve(
    auto_approve_pat: str, repository: Repository, pull_request: PullRequest
) -> None:
    """Approve the Pull Request if the branch creator is the same of the repository owner"""
    pr_commits = pull_request.get_commits()
    first_commit = pr_commits[0]

    branch_owner = first_commit.author
    repository_owner_login = repository.owner.login
    branch_owner_login = branch_owner.login
    allowed_logins = Config.pull_request_manager.auto_approve_logins + [
        repository_owner_login
    ]
    if branch_owner_login not in allowed_logins:
        logger.info(
            'The branch "%s" owner, "%s", is not the same as the repository owner, "%s" '
            "and is not in the auto approve logins list",
            pull_request.head.ref,
            branch_owner_login,
            repository_owner_login,
        )
        return
    if any(review.state == "APPROVED" for review in pull_request.get_reviews()):
        logger.info(
            "Pull Request %s#%d already approved",
            repository.full_name,
            pull_request.number,
        )
        return

    pull_request = repository_helper.get_repo_cached(
        repository.full_name, pat=auto_approve_pat
    ).get_pull(pull_request.number)
    pull_request.create_review(event="APPROVE")
    logger.info(
        "Pull Request %s#%d approved", repository.full_name, pull_request.number
    )
