import logging
import os
import sys

import markdown
import sentry_sdk
from flask import Flask, render_template
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
    """Initialize sentry only if SENTRY_DSN is present"""
    if sentry_dsn := os.getenv("SENTRY_DSN"):
        # Initialize Sentry SDK for error logging
        sentry_sdk.init(
            dsn=sentry_dsn,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            traces_sample_rate=1.0,
            # Set profiles_sample_rate to 1.0 to profile 100%
            # of sampled transactions.
            # We recommend adjusting this value in production.
            profiles_sample_rate=1.0,
        )
        logger.info("Sentry initialized")


app = Flask(__name__)
sentry_init()
webhook_handler.handle_with_flask(app, use_default_index=False)


@webhook_handler.webhook_handler(CheckSuiteRequestedEvent)
def handle(event: CheckSuiteRequestedEvent):
    """
    Handle the Check Suite Requested Event, doing:
     - Creates a Pull Request, if not exists, and/or enable the auto merge flag
    """
    repository = event.repository
    handle_create_pull_request(repository, event.check_suite.head_branch)


@app.route("/", methods=["GET"])
def index():
    return file("README.md")


@app.route("/<path:filename>", methods=["GET"])
def file(filename):
    with open(filename) as f:
        md = f.read()
    body = markdown.markdown(md)
    return render_template("index.html", title="Bartholomew Smith", body=body)
