import logging

from github.Commit import Commit
from github.GitCommit import GitCommit
from github.Repository import Repository

from src.helpers.pull_request import get_or_create_pull_request

logger = logging.getLogger(__name__)


def handle_create_pull_request(repository: Repository, commit: Commit):
    pull_request = get_or_create_pull_request(repository, commit)
    return {"statusCode": 200, "body": "Hello from Lambda!"}
