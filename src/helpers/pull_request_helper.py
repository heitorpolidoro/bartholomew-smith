import logging
from typing import Optional

import github
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config

from src.helpers import repository_helper

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
    except github.GithubException as ghe:
        if ghe.data and any(
            error.get("message")
            == f"No commits between {repository.default_branch} and {branch}"
            for error in ghe.data["errors"]
        ):
            logger.warning(
                "No commits between '%s' and '%s'", repository.default_branch, branch
            )
        else:
            raise
    return None


def update_pull_requests(repository):
    for pull_request in repository.get_pulls(
        state="open", base=repository.default_branch
    ):
        if pull_request.mergeable_state == "behind":
            pull_request.update_branch()


def approve(auto_approve_pat: str, repository: Repository, pull_request: PullRequest):
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
    if any(
        review.user.login == branch_owner_login and review.state == "APPROVED"
        for review in pull_request.get_reviews()
    ):
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
