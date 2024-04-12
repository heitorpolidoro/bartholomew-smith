import threading
import time

from app import make_request


def make_thread_request(request_url, issue_url):  # pragma: no cover
    thread = threading.Thread(target=make_request, args=(request_url, issue_url))
    thread.start()
    time.sleep(1)
