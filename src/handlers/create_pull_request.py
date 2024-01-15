import logging

from github.Repository import Repository

from src.helpers import pull_request

logger = logging.getLogger(__name__)


def handle_create_pull_request(repository: Repository, branch: str):
    pr = pull_request.get_or_create_pull_request(repository, branch)
    pull_request.enable_auto_merge(pr)
