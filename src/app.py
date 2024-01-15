import logging
import os
import sys

import sentry_sdk
from flask import Flask
from githubapp import webhook_handler
from githubapp.events import CheckSuiteRequestedEvent

from src.handlers.create_pull_request import handle_create_pull_request

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


@webhook_handler.webhook_handler(CheckSuiteRequestedEvent)
def handle(event: CheckSuiteRequestedEvent):
    repository = event.repository
    handle_create_pull_request(repository, event.check_suite.head_branch)
