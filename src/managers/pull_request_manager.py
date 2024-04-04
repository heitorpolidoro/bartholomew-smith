import logging

from github import Github
from github.Auth import Token
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config

from src.helpers import pull_request_helper
from src.helpers.repository_helper import get_repo_cached

logger = logging.getLogger(__name__)


def handle_create_pull_request(repository: Repository, branch: str):
    """Creates a Pull Request, if not exists, and/or enable the auto merge flag"""
    pull_request_helper.get_or_create_pull_request(repository, branch).enable_automerge(
        merge_method=Config.pull_request_manager.merge_method
    )


def handle_auto_update_pull_request(repository: Repository, branch: str):
    for pull_request in repository.get_pulls(state="open", base=branch):
        if pull_request.mergeable_state == "behind":
            pull_request.update_branch()


def handle_self_approver(
    owner_pat: str, repository: Repository, pull_request: PullRequest
):
    """Approve the Pull Request if the branch creator is the same of the repository owner"""
    pr_commits = pull_request.get_commits()
    first_commit = pr_commits[0]

    branch_owner = first_commit.author
    if branch_owner.login != repository.owner.login:
        logger.info(
            'The branch "%s" owner, "%s", is not the same as the repository owner, "%s"',
            pull_request.head.ref,
            branch_owner.login,
            repository.owner.login,
        )
        return
    if any(
        review.user.login == branch_owner.login and review.state == "APPROVED"
        for review in pull_request.get_reviews()
    ):
        logger.info(
            "Pull Request %s#%d already approved",
            repository.full_name,
            pull_request.number,
        )
        return

    gh = Github(auth=Token(owner_pat))
    pull_request = get_repo_cached(gh, repository.full_name).get_pull(
        pull_request.number
    )
    pull_request.create_review(event="APPROVE")
    logger.info(
        "Pull Request %s#%d approved", repository.full_name, pull_request.number
    )
