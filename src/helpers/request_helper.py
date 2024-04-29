import threading
import time

import flask
import requests


def make_thread_request(request_url: str, issue_url: str):  # pragma: no cover
    thread = threading.Thread(target=make_request, args=(request_url, issue_url))
    thread.start()
    time.sleep(1)  # To ensure that the thread started


def make_request(request_url: str, issue_url: str):
    requests.post(request_url, json={"issue_url": issue_url})


def get_request_url(endpoint: str) -> str:
    return flask.request.base_url + flask.url_for(endpoint)
