from unittest.mock import Mock, call, patch

import pytest
from github import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config
from githubapp.event_check_run import CheckRunConclusion, CheckRunStatus
from githubapp.events import CheckSuiteRequestedEvent, CheckSuiteRerequestedEvent

from tests.managers.pull_request_manager import IGNORING_TITLE, ManagerCheckRunTestCase


class TestEnableAutoMergeCheckRun(ManagerCheckRunTestCase):
    event_types = [CheckSuiteRequestedEvent, CheckSuiteRerequestedEvent]

    def setup_method(self, method):
        super().setup_method(method)

        def repository_get_branch(self_, branch_name):
            return Mock(name=branch_name, protected=branch_name == self_.default_branch)

        self.pull_request = Mock(
            spec=PullRequest,
            number=123,
            title="Pull Request Title",
            user=Mock(login=Config.BOT_NAME),
        )
        self.patch(patch.object(Repository, "get_branch", repository_get_branch))
        self.patch(
            patch.object(Repository, "get_pulls", return_value=[self.pull_request])
        )

    @staticmethod
    def setup_config():
        Config.release_manager.enabled = False
        Config.issue_manager.enabled = False
        Config.pull_request_manager.set_values(
            enabled=True,
            create_pull_request=False,
            link_issue=False,
            enable_auto_merge=True,
            merge_method="SQUASH",
            auto_approve=False,
            auto_approve_logins=[],
            auto_update=False,
        )

    def test_when_head_branch_is_not_default_branch(self, event_type):
        self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

        self.assert_managers_calls(
            pull_request=self.pull_request,
        )

        self.assert_managers_check_run_calls(
            enable_auto_merge_calls=[
                call(title="Enabling auto-merge", status=CheckRunStatus.IN_PROGRESS),
                call(title="Auto-merge enabled", conclusion=CheckRunConclusion.SUCCESS),
            ]
        )

        self.assert_last_check_run_call(
            "Pull Request Manager",
            conclusion=CheckRunConclusion.SUCCESS,
            title="Done",
            summary="Create Pull Request: Disabled\n"
            "Enable auto-merge: Auto-merge enabled\n"
            "Auto Update Pull Requests: Disabled",
            text=None,
            status=None,
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_head_branch_is_default_branch(self, event_type):
        self.deliver(event_type, check_suite={"head_branch": "default_branch"})

        self.assert_managers_calls(
            pull_request=None,
        )

        self.assert_managers_check_run_calls(
            enable_auto_merge_calls=[
                call(
                    title=IGNORING_TITLE,
                    conclusion=CheckRunConclusion.SKIPPED,
                    update_check_run=False,
                ),
            ]
        )

        self.assert_last_check_run_call(
            "Pull Request Manager",
            conclusion=CheckRunConclusion.SKIPPED,
            title="Skipped",
            summary="Create Pull Request: Disabled\n"
            f"Enable auto-merge: {IGNORING_TITLE}\n"
            "Auto Update Pull Requests: Disabled",
            text=None,
            status=None,
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_the_default_branch_is_not_protected(self, event_type):
        with patch.object(
            Repository,
            "get_branch",
            return_value=Mock(name="default_branch", protected=False),
        ):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            self.assert_managers_calls(
                pull_request=None,
            )

            self.assert_managers_check_run_calls(
                enable_auto_merge_calls=[
                    call(
                        title="Enabling auto-merge", status=CheckRunStatus.IN_PROGRESS
                    ),
                    call(
                        title="Cannot enable auto-merge in a repository with no protected branch.",
                        summary="Check [Enabling auto-merge](https://docs.github.com/en/pull-requests/collaborating-"
                        "with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-"
                        "a-pull-request#enabling-auto-merge) for more information",
                        conclusion=CheckRunConclusion.FAILURE,
                    ),
                ]
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.FAILURE,
                title="Cannot enable auto-merge in a repository with no protected branch.",
                summary="Create Pull Request: Disabled\n"
                "Enable auto-merge: Cannot enable auto-merge in a repository with no protected branch.\n"
                "Check [Enabling auto-merge](https://docs.github.com/en/pull-requests/collaborating-"
                "with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-"
                "a-pull-request#enabling-auto-merge) for more information\n"
                "Auto Update Pull Requests: Disabled",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()

    @pytest.mark.parametrize(
        "exception",
        [
            GithubException(500, data={"errors": [{"message": "Error"}]}),
            Exception("Error"),
        ],
    )
    def test_when_error_on_enabling_auto_merge(self, event_type, exception):
        with patch.object(self.pull_request, "enable_automerge", side_effect=exception):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            self.assert_managers_calls(
                pull_request=self.pull_request,
            )

            self.assert_managers_check_run_calls(
                enable_auto_merge_calls=[
                    call(
                        title="Enabling auto-merge", status=CheckRunStatus.IN_PROGRESS
                    ),
                    call(
                        title="Enabling auto-merge failure",
                        summary="Error",
                        conclusion=CheckRunConclusion.FAILURE,
                    ),
                ]
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.FAILURE,
                title="Enabling auto-merge failure",
                summary="Create Pull Request: Disabled\n"
                "Enable auto-merge: Enabling auto-merge failure\n"
                "Error\n"
                "Auto Update Pull Requests: Disabled",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()

    def test_when_there_is_no_pull_request(self, event_type):
        with patch.object(Repository, "get_pulls", return_values=[]):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            self.assert_managers_calls(
                pull_request=None,
            )

            self.assert_managers_check_run_calls(
                enable_auto_merge_calls=[
                    call(
                        title="Enabling auto-merge", status=CheckRunStatus.IN_PROGRESS
                    ),
                    call(
                        title="Enabling auto-merge failure",
                        summary="There is no Pull Request for the head branch feature_branch",
                        conclusion=CheckRunConclusion.FAILURE,
                    ),
                ]
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.FAILURE,
                title="Enabling auto-merge failure",
                summary="Create Pull Request: Disabled\n"
                "Enable auto-merge: Enabling auto-merge failure\n"
                "There is no Pull Request for the head branch feature_branch\n"
                "Auto Update Pull Requests: Disabled",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()
