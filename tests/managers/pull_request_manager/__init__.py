from unittest.mock import call

from githubapp import Config
from githubapp.event_check_run import CheckRunConclusion, CheckRunStatus
from githubapp.test_helper import TestCase

from app import app
from src.helpers import pull_request_helper

IGNORING_TITLE = "In the default branch 'default_branch', ignoring."
# TODO Reordenar os metodos

__tracebackhide__ = True


class ManagerCheckRunTestCase(TestCase):
    client = app.test_client()

    def teardown_method(self, method):
        super().teardown_method(method)
        pull_request_helper.cache.clear()

    # noinspection PyAttributeOutsideInit
    def update_configs(self):
        config = Config.pull_request_manager
        self.pull_request_enabled = config.enabled
        self.create_pull_request_enabled = (
            self.pull_request_enabled and config.create_pull_request
        )
        self.enable_auto_merge_enabled = (
            self.pull_request_enabled and config.enable_auto_merge
        )
        self.auto_update_enabled = self.pull_request_enabled and config.auto_update
        self.auto_approve_enabled = self.pull_request_enabled and config.auto_approve

        # Config.release_manager.enabled = False
        # Config.issue_manager.enabled = False
        # Config.pull_request_manager.set_values(
        #     link_issue=False,
        #     merge_method="SQUASH",
        #     auto_approve_logins=[],
        # )

    def assert_managers_calls(self, **params):
        self.update_configs()
        self.assert_pull_request_manager_calls(**params)

    def assert_managers_check_run_calls(self, **params):
        self.update_configs()
        self.assert_pull_request_manager_check_run_calls(**params)

    def assert_pull_request_manager_calls(
        self,
        create_pull_call=None,
        pull_request=None,
        pull_requests_auto_update=None,
        **_,
    ):
        # Create Pull Request
        self.assert_create_pull_request_calls(create_pull_call)

        # Enable Auto Merge
        if pull_request:
            self.assert_enable_auto_merge_calls(pull_request)

        # Auto Update Pull Requests
        if pull_request:
            # Never update this pull request
            pull_request.update_branch.assert_not_called()
        self.assert_auto_update_calls(pull_requests_auto_update)

        # Auto Approve
        if pull_request:
            self.assert_auto_approve_calls(pull_request)

    def assert_release_manager_calls(self, **_):
        ...
        # # Create Pull Request
        # self.assert_create_pull_request_calls(create_pull_call)
        #
        # # Enable Auto Merge
        # if pull_request:
        #     self.assert_enable_auto_merge_calls(pull_request)
        #
        # # Auto Update Pull Requests
        # if pull_request:
        #     # Never update this pull request
        #     pull_request.update_branch.assert_not_called()
        # self.assert_auto_update_calls(pull_requests_auto_update)
        #
        # # Auto Approve
        # if pull_request:
        #     self.assert_auto_approve_calls(pull_request)

    def assert_auto_approve_calls(self, pull_request):
        if self.auto_approve_enabled:
            assert False, "Not implemented"
        else:
            pull_request.create_review.assert_not_called()

    def assert_auto_update_calls(self, pull_requests_auto_update):
        for pr, should_update in pull_requests_auto_update or []:
            if self.auto_update_enabled and should_update:
                pr.update_branch.assert_called_once()
            else:
                pr.update_branch.assert_not_called()

    def assert_enable_auto_merge_calls(self, pull_request):
        if self.enable_auto_merge_enabled:
            pull_request.enable_automerge.assert_called_once_with(
                merge_method=Config.pull_request_manager.merge_method
            )
        else:
            pull_request.enable_automerge.assert_not_called()

    # noinspection PyUnresolvedReferences
    def assert_create_pull_request_calls(self, create_pull_call):
        if self.create_pull_request_enabled and create_pull_call:
            self.event.repository.create_pull.assert_called_once_with(
                *create_pull_call.args, **create_pull_call.kwargs
            )
        else:
            self.event.repository.create_pull.assert_not_called()

    def assert_subrun_calls_when_disabled(self, check_run_name: str, subrun_name: str):
        self.assert_subrun_calls(
            check_run_name,
            subrun_name,
            [
                call(title="Disabled", conclusion=CheckRunConclusion.SKIPPED),
            ],
        )

    def assert_pull_request_manager_check_run_calls(
        self,
        create_pull_request_calls=None,
        enable_auto_merge_calls=None,
        auto_update_pull_requests_calls=None,
        **_,
    ):
        self.assert_check_run_calls(
            "Pull Request Manager",
            [call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS)],
        )
        if self.create_pull_request_enabled:
            self.assert_subrun_calls(
                "Pull Request Manager",
                "Create Pull Request",
                create_pull_request_calls,
            )
        else:
            self.assert_subrun_calls_when_disabled(
                "Pull Request Manager",
                "Create Pull Request",
            )

        if self.enable_auto_merge_enabled:
            self.assert_subrun_calls(
                "Pull Request Manager", "Enable auto-merge", enable_auto_merge_calls
            )
        else:
            self.assert_subrun_calls_when_disabled(
                "Pull Request Manager",
                "Enable auto-merge",
            )

        if self.auto_update_enabled:
            self.assert_subrun_calls(
                "Pull Request Manager",
                "Auto Update Pull Requests",
                auto_update_pull_requests_calls,
            )
        else:
            self.assert_subrun_calls_when_disabled(
                "Pull Request Manager",
                "Auto Update Pull Requests",
            )
