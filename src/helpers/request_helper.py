"""
Methods to help make requests
Separating in a module to help in tests
"""
import threading
import time
from typing import NoReturn

import flask
import requests


# pragma: no cover
def make_thread_request(request_url: str, issue_url: str) -> NoReturn:
    """ Make a request through a thread """
    thread = threading.Thread(target=make_request, args=(request_url, issue_url))
    thread.start()
    # To ensure that the thread started
    time.sleep(1)


def make_request(request_url: str, issue_url: str) -> NoReturn:
    """ Make a post request """
    requests.post(request_url, json={"issue_url": issue_url}, timeout=60)


def get_request_url(endpoint: str) -> str:
    """ Get the url for a endpoint """
    return flask.request.base_url + flask.url_for(endpoint)
