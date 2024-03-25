import logging
import os
import sys
import threading
import time
from typing import Union

import markdown
import sentry_sdk
from flask import Flask, render_template, request
from flask.cli import load_dotenv
from githubapp import Config, webhook_handler
from githubapp.events import (
    CheckSuiteCompletedEvent,
    CheckSuiteRequestedEvent,
    CheckSuiteRerequestedEvent,
    IssueEditedEvent,
    IssueOpenedEvent,
)
from githubapp.events.issues import IssueClosedEvent

from src.managers.issue_manager import (
    handle_close_tasklist,
    parse_issue_and_create_tasks,
    process_jobs,
)
from src.managers.pull_request_manager import (
    handle_create_pull_request,
    handle_self_approver,
)
from src.managers.release_manager import handle_release

logging.basicConfig(
    stream=sys.stdout,
    format="%(levelname)s:%(module)s:%(funcName)s:%(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# TODO move to github-app-handler
Config.BOT_NAME = "bartholomew-smith[bot]"


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
    app, use_default_index=False, config_file=".bartholomew.yaml"
)
load_dotenv()
Config.create_config("pull_request_manager", enabled=True, merge_method="SQUASH")
Config.create_config("release_manager", enabled=True)
Config.create_config("issue_manager", enabled=True)


@webhook_handler.add_handler(CheckSuiteRequestedEvent)
@webhook_handler.add_handler(CheckSuiteRerequestedEvent)
def handle_check_suite_requested(event: CheckSuiteRequestedEvent):
    """
    Handle the Check Suite Requested Event, doing:
     - Creates a Pull Request, if not exists, and/or enable the auto merge flag
    """
    repository = event.repository
    if Config.pull_request_manager.enabled:
        handle_create_pull_request(repository, event.check_suite.head_branch)
    if Config.release_manager.enabled:
        handle_release(event)


@webhook_handler.add_handler(IssueOpenedEvent)
@webhook_handler.add_handler(IssueEditedEvent)
def handle_issue(event: Union[IssueOpenedEvent, IssueEditedEvent]):
    """
    Handle the Issues events, handling the tasklist and add the issue to the main project if
    configured to
    :param event:
    :return:
    """
    if Config.issue_manager.enabled and event.issue and event.issue.body:
        parse_issue_and_create_tasks(
            event.issue, event.hook_installation_target_id, event.installation_id
        )
    url = request.url + "process_jobs"
    thread = threading.Thread(target=make_request, args=(url,))
    thread.start()
    time.sleep(1)
    # add_to_project(event)


@app.route("/process_jobs", methods=["GET"])
def process_jobs_endpoint():
    process_jobs()
    return "OK"


@webhook_handler.add_handler(IssueClosedEvent)
def handle_issue_closed(event: IssueClosedEvent):
    """
    Handle the Issue Closed events, closing the issues in the task list
    :param event:
    :return:
    """
    if Config.issue_manager.enabled and event.issue and event.issue.body:
        handle_close_tasklist(event)


@webhook_handler.add_handler(CheckSuiteCompletedEvent)
def handle_check_suite_completed(event: CheckSuiteCompletedEvent):
    """
    Handle the Check Suite Completed Event, doing:
     - Creates a Pull Request, if not exists, and/or enable the auto merge flag
    """
    if owner_pat := os.getenv("OWNER_PAT"):
        repository = event.repository
        for pull_request in event.check_suite.pull_requests:
            handle_self_approver(owner_pat, repository, pull_request)


@app.route("/", methods=["GET"])
def index():
    """Return the index homepage"""
    with open("README.md") as f:
        md = f.read()
    body = markdown.markdown(md)
    title = "Bartholomew Smith"
    return render_template("index.html", title=title, body=body)


@app.route("/marketplace", methods=["POST"])
def marketplace():
    """Marketplace events"""
    logger.info(f"Marketplace event: {request.json}")
    print(f"Marketplace event: {request.json}")
    return "OK"


def make_request(url):
    import requests

    print(url)
    requests.get(url)


@app.route("/sleep/<secs>")
def sleep(secs):
    import threading
    import time

    secs = float(secs)

    if secs < 15:
        url = "/".join(request.url.split("/")[:-1] + [str(secs + 1)])
        print(f"Requesting {url}")
        thread = threading.Thread(target=make_request, args=(url,))
        thread.start()

    print(f"---------------------- Sleeping for {secs} seconds")
    time.sleep(float(secs))
    print(f"---------------------- Done sleeping for {secs} seconds")
    return "OK"
