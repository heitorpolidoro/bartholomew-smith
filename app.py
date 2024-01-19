import logging
import os
import sys

import markdown
import sentry_sdk
from flask import Flask, abort, render_template
from githubapp import Config, webhook_handler
from githubapp.events import (
    CheckSuiteRequestedEvent,
    CheckSuiteRerequestedEvent,
    IssueEditedEvent,
    IssueOpenedEvent,
)
from githubapp.events.issues import IssueClosedEvent, IssuesEvent

from src.managers.issue import handle_close_tasklist, handle_tasklist
from src.managers.pull_request import handle_create_pull_request
from src.managers.release import handle_release

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
webhook_handler.handle_with_flask(
    app, use_default_index=False, config_file="bartholomew.yaml"
)


@webhook_handler.add_handler(CheckSuiteRequestedEvent)
@webhook_handler.add_handler(CheckSuiteRerequestedEvent)
def handle_check_suite_requested(event: CheckSuiteRequestedEvent):
    """
    Handle the Check Suite Requested Event, doing:
     - Creates a Pull Request, if not exists, and/or enable the auto merge flag
    """
    repository = event.repository
    if Config.is_pull_request_manager_enabled:
        handle_create_pull_request(repository, event.check_suite.head_branch)
    if Config.is_release_manager_enabled:
        handle_release(event)


@webhook_handler.add_handler(IssueOpenedEvent)
@webhook_handler.add_handler(IssueEditedEvent)
@webhook_handler.add_handler(IssueClosedEvent)
def handle_issue(event: IssuesEvent):
    """
    TODO update
    Handle the IssueOpened and IssueEdited events, handling the tasklist and add the issue to the main project if
    configured to
    :param event:
    :return:
    """
    if Config.is_issue_manager_enabled and event.issue and event.issue.body:
        if isinstance(event, IssueClosedEvent):
            handle_close_tasklist(event)
        else:
            handle_tasklist(event)
    # add_to_project(event)


@app.route("/", methods=["GET"])
def index():
    """Return the index homepage"""
    return file("README.md")


@app.route("/<path:filename>", methods=["GET"])
def file(filename):
    """Convert a md file into HTML and return it"""
    allowed_files = {f: f for f in ["README.md", "pull-request.md"]}
    if filename not in allowed_files:
        abort(404)
    with open(allowed_files[filename]) as f:
        md = f.read()
    body = markdown.markdown(md)
    title = "Bartholomew Smith"
    if filename != "README.md":
        title += f" - {filename.replace('-', ' ').replace('.md', '').title()}"
    return render_template("index.html", title=title, body=body)
