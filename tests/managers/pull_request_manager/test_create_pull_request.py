from unittest.mock import Mock, patch, call, ANY

from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config
from githubapp.event_check_run import CheckRunStatus, CheckRunConclusion
from githubapp.events import CheckSuiteRequestedEvent, CheckSuiteRerequestedEvent

from tests.managers.pull_request_manager import ManagerCheckRunTestCase, IGNORING_TITLE


class TestCreatePullRequestCheckRun(ManagerCheckRunTestCase):
    event_types = [CheckSuiteRequestedEvent, CheckSuiteRerequestedEvent]

    @staticmethod
    def setup_config():
        Config.release_manager.enabled = False
        Config.issue_manager.enabled = False
        Config.pull_request_manager.set_values(
            enabled=True,
            create_pull_request=True,
            link_issue=False,
            enable_auto_merge=False,
            merge_method="SQUASH",
            auto_approve=False,
            auto_approve_logins=[],
            auto_update=False,
        )

    def test_when_head_branch_is_not_default_branch(self, event_type):
        """Create the Pull Request"""
        pull_request = Mock(spec=PullRequest)
        with patch.object(Repository, "create_pull", return_value=pull_request):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            self.assert_managers_calls(
                create_pull_call=call(
                    "default_branch",
                    "feature_branch",
                    title="feature_branch",
                    body="Pull Request automatically created",
                    draft=False,
                ),
                pull_request=pull_request,
            )

            self.assert_managers_check_run_calls(
                create_pull_request_calls=[
                    call(title="Creating Pull Request", status=CheckRunStatus.IN_PROGRESS),
                    call(title="Pull Request created", conclusion=CheckRunConclusion.SUCCESS),
                ]
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Done",
                summary="Create Pull Request: Pull Request created\n"
                "Enable auto-merge: Disabled\n"
                "Auto Update Pull Requests: Disabled",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()

    def test_when_head_branch_is_the_default_branch(self, event_type):
        """Don't create the Pull Request"""
        self.deliver(event_type, check_suite={"head_branch": "default_branch"})

        self.assert_managers_calls()

        self.assert_managers_check_run_calls(
            create_pull_request_calls=[
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
            summary=f"Create Pull Request: {IGNORING_TITLE}\n"
            "Enable auto-merge: Disabled\n"
            "Auto Update Pull Requests: Disabled",
            text=None,
            status=None,
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_a_pull_request_already_exists(self, event_type):
        """Pull Request already exists"""
        pull_request = Mock(spec=PullRequest)
        with patch.object(
            Repository,
            "create_pull",
            side_effect=self.create_github_exception(
                "A pull request already exists for heitorpolidoro:feature_branch."
            ),
        ):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            self.assert_managers_calls(
                create_pull_call=call(
                    "default_branch",
                    "feature_branch",
                    title="feature_branch",
                    body="Pull Request automatically created",
                    draft=False,
                ),
                pull_request=pull_request,
            )

            self.assert_managers_check_run_calls(
                create_pull_request_calls=[
                    call(title="Creating Pull Request", status=CheckRunStatus.IN_PROGRESS),
                    call(title="Pull Request already exists", conclusion=CheckRunConclusion.SUCCESS),
                ]
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Done",
                summary="Create Pull Request: Pull Request already exists\n"
                "Enable auto-merge: Disabled\n"
                "Auto Update Pull Requests: Disabled",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()

    def test_when_another_github_exception_in_pull_request_creation(self, event_type):
        """Don't Create Pull Request"""
        with patch.object(
            Repository,
            "create_pull",
            side_effect=self.create_github_exception("Other GithubException"),
        ):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            self.assert_managers_calls(
                create_pull_call=call(
                    "default_branch",
                    "feature_branch",
                    title="feature_branch",
                    body="Pull Request automatically created",
                    draft=False,
                ),
            )

            self.assert_managers_check_run_calls(
                create_pull_request_calls=[
                    call(title="Creating Pull Request", status=CheckRunStatus.IN_PROGRESS),
                    call(
                        title="Pull Request creation failure",
                        summary="Other GithubException",
                        conclusion=CheckRunConclusion.FAILURE,
                    ),
                ]
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.FAILURE,
                title="Pull Request creation failure",
                summary="Create Pull Request: Pull Request creation failure\n"
                "Other GithubException\n"
                "Enable auto-merge: Disabled\n"
                "Auto Update Pull Requests: Disabled",
                text=ANY,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()

    def test_when_there_is_an_error_on_creating_the_pull_request(self, event_type):
        """Error to create Pull Request"""
        with patch.object(
            Repository,
            "create_pull",
            side_effect=Exception("Other Error"),
        ):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            self.assert_managers_calls(
                create_pull_call=call(
                    "default_branch",
                    "feature_branch",
                    title="feature_branch",
                    body="Pull Request automatically created",
                    draft=False,
                ),
            )

            self.assert_managers_check_run_calls(
                create_pull_request_calls=[
                    call(title="Creating Pull Request", status=CheckRunStatus.IN_PROGRESS),
                    call(
                        title="Pull Request creation failure",
                        summary="Other Error",
                        conclusion=CheckRunConclusion.FAILURE,
                    ),
                ]
            )

            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.FAILURE,
                title="Pull Request creation failure",
                summary="Create Pull Request: Pull Request creation failure\n"
                "Other Error\n"
                "Enable auto-merge: Disabled\n"
                "Auto Update Pull Requests: Disabled",
                text=ANY,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()
