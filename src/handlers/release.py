from githubapp.events import CheckSuiteRequestedEvent


def handle_release(event: CheckSuiteRequestedEvent):
    repository = event.repository

    head_sha = event.check_suite.head_sha

    event.start_check_run(
        "Releaser", head_sha, title="Checking for release command"
    )

    while True:
        head_commit = repository.get_commit(head_sha)
    #     commit
