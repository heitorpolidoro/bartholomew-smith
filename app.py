import json
import logging
import os
import sys
from typing import Union

import markdown
import sentry_sdk
from flask import Flask, render_template, request
from flask.cli import load_dotenv
from github import Github
from githubapp import Config, webhook_handler
from githubapp.events import (
    CheckSuiteCompletedEvent,
    CheckSuiteRequestedEvent,
    CheckSuiteRerequestedEvent,
    IssueEditedEvent,
    IssueOpenedEvent,
)
from githubapp.events.issues import IssueClosedEvent
from githubapp.webhook_handler import _get_auth

from src.helpers.issue_helper import has_tasklist, issue_ref
from src.managers.issue_manager import handle_close_tasklist, handle_task_list
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
    import boto3

    sqs = boto3.client("sqs", region_name="us-east-1")

    if Config.issue_manager.enabled and event.issue and event.issue.body:
        issue = event.issue
        issue_body = issue.body
        if has_tasklist(issue_body):
            issue_comment = issue.create_comment(
                "I'll manage the issues in the next minutes (sorry, free server :disappointed: )"
            )
            sqs.send_message(
                QueueUrl=os.getenv("TASKLIST_QUEUE"),
                MessageBody=json.dumps(
                    {
                        "headers": dict(request.headers),
                        "issue": issue_ref(issue),
                        "installation_id": request.json["installation"]["id"],
                        "issue_comment_id": issue_comment.id,
                    }
                ),
            )
    # add_to_project(event)


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


@app.route("/handle_task_list", methods=["POST"])
def handle_message():
    body = request.json
    headers = body["headers"]
    print(body)
    issue = body["issue"]

    hook_installation_target_id = int(headers["X-Github-Hook-Installation-Target-Id"])
    installation_id = int(body["installation_id"])
    auth = _get_auth(hook_installation_target_id, installation_id)
    gh = Github(auth=auth)
    handle_task_list(gh, issue, issue_comment_id=body["issue_comment_id"])
    return "OK"


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

    if secs < 30:
        url = "/".join(request.url.split("/")[:-1] + [str(secs + 1)])
        logger.info(f"Requesting {url}")
        # url = f"https://bartholomew-smith.vercel.app/sleep/{secs+1}"
        thread = threading.Thread(target=make_request, args=(url,))
        thread.start()

    logger.info(f"---------------------- Sleeping for {secs} seconds")
    time.sleep(float(secs))
    logger.info(f"---------------------- Done sleeping for {secs} seconds")
    return "OK"
