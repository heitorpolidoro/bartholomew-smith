import logging

from github.Repository import Repository
from githubapp import Config

from src.helpers import pull_request

logger = logging.getLogger(__name__)


def handle_create_pull_request(repository: Repository, branch: str):
    """Creates a Pull Request, if not exists, and/or enable the auto merge flag"""
    if repository.default_branch != branch:
        pull_request.get_or_create_pull_request(repository, branch).enable_automerge(
            merge_method=Config.pull_request_manager.merge_method
        )
