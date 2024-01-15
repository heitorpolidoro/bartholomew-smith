import logging
import os
import sys

import sentry_sdk
from flask import Flask

from githubapp import webhook_handler
from githubapp.events import CreateBranchEvent
from src.pull_request_handler import get_or_create_pr, enable_auto_merge

logging.basicConfig(
    stream=sys.stdout,
    format="%(levelname)s:%(module)s:%(funcName)s:%(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def sentry_init():
    if sentry_dns := os.getenv("SENTRY_DSN"):  # pragma: no cover
        # Initialize Sentry SDK for error logging
        sentry_sdk.init(
            dsn=sentry_dns,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            traces_sample_rate=1.0,
            # Set profiles_sample_rate to 1.0 to profile 100%
            # of sampled transactions.
            # We recommend adjusting this value in production.
            profiles_sample_rate=1.0,
        )
        logger.info("Sentry initialized")


app = Flask("Bartholomew Smith")
sentry_init()
webhook_handler.handle_with_flask(app)


@webhook_handler.webhook_handler(CreateBranchEvent)
def create_branch_handler(event: CreateBranchEvent) -> None:
    repository = event.repository
    branch = event.ref
    logger.info(
        "Branch %s:%s created in %s",
        repository.owner.login,
        branch,
        repository.full_name,
    )
    if pr := get_or_create_pr(repository, branch):
        enable_auto_merge(pr)
