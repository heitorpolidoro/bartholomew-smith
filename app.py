"""This module contains the main application logic."""

import logging
import os
import sys
from multiprocessing import Process
from typing import NoReturn

import markdown
import sentry_sdk
from flask import Flask, Response, jsonify, render_template, request
from flask.cli import load_dotenv
from githubapp import Config, webhook_handler
from githubapp.events import (
    CheckSuiteCompletedEvent,
    CheckSuiteRequestedEvent,
    CheckSuiteRerequestedEvent,
    IssueEditedEvent,
    IssueOpenedEvent,
)
from githubapp.events.issues import IssueClosedEvent, IssuesEvent

from config import default_configs
from src.helpers import request_helper
from src.managers import issue_manager, pull_request_manager, release_manager
from src.models import IssueJobStatus
from src.services import IssueJobService

logging.basicConfig(
    stream=sys.stdout,
    format="%(levelname)s:%(module)s:%(funcName)s:%(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def sentry_init() -> NoReturn:  # pragma: no cover
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
default_configs()


@webhook_handler.add_handler(CheckSuiteRequestedEvent)
@webhook_handler.add_handler(CheckSuiteRerequestedEvent)
def handle_check_suite_requested(event: CheckSuiteRequestedEvent) -> NoReturn:
    """
    handle the Check Suite Request and Rerequest events
    Calling the Pull Request manager to:
    - Create Pull Request
    - Enable auto merge
    - Update Pull Requests
    - Auto approve Pull Requests
    """
    pull_request_manager.manage(event)
    release_manager.manage(event)
    pull_request_manager.auto_approve(event)


@webhook_handler.add_handler(CheckSuiteCompletedEvent)
def handle_check_suite_completed(event: CheckSuiteCompletedEvent) -> NoReturn:
    """
    handle the Check Suite Request and Rerequest events
    Calling the Pull Request manager to:
    - Create Pull Request
    - Enable auto merge
    - Update Pull Requests
    - Auto approve Pull Requests
    """
    pull_request_manager.auto_update_pull_requests(event)


@webhook_handler.add_handler(IssueOpenedEvent)
@webhook_handler.add_handler(IssueEditedEvent)
@webhook_handler.add_handler(IssueClosedEvent)
def handle_issue(event: IssuesEvent) -> NoReturn:
    """
    handle the Issues Open, Edit and Close events
    Calling the Issue Manager to:
    - Create issues from task list
    - Close/Reopen issues from the checkbox in the task list

    """
    if issue_job := issue_manager.manage(event):
        if issue_job.issue_job_status != IssueJobStatus.RUNNING:
            process_jobs_endpoint(issue_job.issue_url)


@app.route("/process_jobs", methods=["POST"])
def process_jobs_endpoint(issue_url: str = None) -> tuple[Response, int]:
    """Process the jobs for the given issue_url"""
    issue_url = issue_url or request.get_json(force=True).get("issue_url")
    if not issue_url:
        return jsonify({"error": "issue_url is required"}), 400
    process = Process(target=issue_manager.process_jobs, args=(issue_url,))
    process.start()
    process.join(float(Config.TIMEOUT))
    if issue_job := next(iter(IssueJobService.filter(issue_url=issue_url)), None):
        if process.is_alive():
            IssueJobService.update(issue_job, issue_job_status=IssueJobStatus.PENDING)
            request_helper.make_thread_request(
                request_helper.get_request_url("process_jobs_endpoint"), issue_url
            )
        process.terminate()
        return jsonify({"status": issue_job.issue_job_status.value}), 200
    return jsonify({"error": f"IssueJob for {issue_url=} not found"}), 404


@app.route("/", methods=["GET"])
def index() -> str:  # pragma: no cover
    """Return the index homepage"""
    with open("README.md") as f:
        md = f.read()
    body = markdown.markdown(md)
    title = "Bartholomew Smith"
    return render_template("index.html", title=title, body=body)


@app.route("/marketplace", methods=["POST"])
def marketplace() -> str:  # pragma: no cover
    """Marketplace events"""
    logger.info(f"Marketplace event: {request.json}")
    print(f"Marketplace event: {request.json}")
    return "OK"


def create_tables() -> str:  # pragma: no cover
    """Create the database tables"""
    from src.helpers.db_helper import BaseModelService

    for subclass in BaseModelService.__subclasses__():
        logger.info(f"Creating table for {subclass.clazz.__name__}")
        subclass.create_table()
    return "OK"
