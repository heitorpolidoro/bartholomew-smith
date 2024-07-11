from unittest.mock import Mock, call, patch

import pytest
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config
from githubapp.event_check_run import CheckRunConclusion, CheckRunStatus
from githubapp.events import CheckSuiteRequestedEvent, CheckSuiteRerequestedEvent

from tests.managers.pull_request_manager import ManagerCheckRunTestCase


class TestEnableAutoMergeCheckRun(ManagerCheckRunTestCase):
    event_types = [CheckSuiteRequestedEvent, CheckSuiteRerequestedEvent]

    @staticmethod
    def setup_config():
        Config.release_manager.enabled = False
        Config.issue_manager.enabled = False
        Config.pull_request_manager.set_values(
            enabled=True,
            create_pull_request=False,
            link_issue=False,
            enable_auto_merge=False,
            merge_method="SQUASH",
            auto_approve=False,
            auto_approve_logins=[],
            auto_update=True,
        )

    def test_update_only_behind(self, event_type):
        pull_requests = [
            (
                Mock(
                    spec=PullRequest,
                    mergeable_state="behind",
                    number=1,
                    title="PR Title 1",
                ),
                True,
            ),
            (
                Mock(
                    spec=PullRequest,
                    mergeable_state="not_behind",
                    number=2,
                    title="PR Title 2",
                ),
                False,
            ),
            (
                Mock(
                    spec=PullRequest,
                    mergeable_state="behind",
                    number=3,
                    title="PR Title 3",
                ),
                True,
            ),
        ]
        with (patch.object(Repository, "get_pulls", return_value=[pr[0] for pr in pull_requests]),):
            self.deliver(event_type, check_suite={"head_branch": "default_branch"})

            self.assert_managers_calls(pull_requests_auto_update=pull_requests)

            self.assert_managers_check_run_calls(
                auto_update_pull_requests_calls=[
                    call(
                        title="Updating Pull Requests",
                        status=CheckRunStatus.IN_PROGRESS,
                    ),
                    call(
                        title="Pull Requests Updated",
                        summary="#1 PR Title 1\n#3 PR Title 3",
                        conclusion=CheckRunConclusion.SUCCESS,
                    ),
                ],
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Done",
                summary="Create Pull Request: Disabled\n"
                "Enable auto-merge: Disabled\n"
                "Auto Update Pull Requests: Pull Requests Updated\n"
                "#1 PR Title 1\n#3 PR Title 3",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()

    @pytest.mark.parametrize(
        "pull_requests",
        [
            [
                (
                    Mock(
                        spec=PullRequest,
                        mergeable_state="not_behind",
                        number=2,
                        title="PR Title 2",
                    ),
                    False,
                )
            ],
            [],
        ],
        ids=[
            "No behind Pull Requests",
            "No Pull Requests",
        ],
    )
    def test_when_there_is_no_pull_request_to_update(self, event_type, pull_requests):
        with (patch.object(Repository, "get_pulls", return_value=[pr[0] for pr in pull_requests]),):
            self.deliver(event_type, check_suite={"head_branch": "default_branch"})

            self.assert_managers_calls(pull_requests_auto_update=pull_requests)

            self.assert_managers_check_run_calls(
                auto_update_pull_requests_calls=[
                    call(
                        title="Updating Pull Requests",
                        status=CheckRunStatus.IN_PROGRESS,
                    ),
                    call(
                        title="No Pull Requests Updated",
                        conclusion=CheckRunConclusion.SUCCESS,
                    ),
                ],
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Done",
                summary="Create Pull Request: Disabled\n"
                "Enable auto-merge: Disabled\n"
                "Auto Update Pull Requests: No Pull Requests Updated",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()
