import logging

from github.Auth import Token
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config

from src.helpers import pull_request_helper

from github import Github

logger = logging.getLogger(__name__)


def handle_create_pull_request(repository: Repository, branch: str):
    """Creates a Pull Request, if not exists, and/or enable the auto merge flag"""
    if repository.default_branch != branch:
        pull_request_helper.get_or_create_pull_request(repository, branch).enable_automerge(
            merge_method=Config.pull_request_manager.merge_method
        )


def handle_self_approver(
    owner_pat: str, repository: Repository, pull_request: PullRequest
):
    pr_commits = pull_request.get_commits()
    first_commit = pr_commits[0]

    branch_owner = first_commit.author
    if branch_owner.login != repository.owner.login:
        logger.info(
            f'The branch "{pull_request.head.ref}" owner, "{branch_owner.login}", '
            f'is not the same as the repository owner, "{repository.owner.login}"'
        )
        return
    if any(
            review.user.login == branch_owner.login and review.state == "APPROVED"
            for review in pull_request.get_reviews()
    ):
        logger.info(f"Pull Request {repository.full_name}#{pull_request.number} already approved")
        return

    gh = Github(auth=Token(owner_pat))
    pull_request = gh.get_repo(repository.full_name).get_pull(pull_request.number)
    pull_request.create_review(event="APPROVE")
    logger.info(f"Pull Request {repository.full_name}#{pull_request.number} approved")
