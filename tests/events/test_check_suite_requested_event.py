from unittest.mock import patch, Mock

from github.PullRequest import PullRequest
from github.Repository import Repository

from app import app
from githubapp import Config
from githubapp.event_check_run import CheckRunConclusion
from githubapp.events import (
    CheckSuiteRequestedEvent,
    CheckSuiteRerequestedEvent,
)
from githubapp.test_helper import TestCase
from src.helpers import pull_request_helper

IGNORING_TITLE = "In the default branch 'default_branch', ignoring."


class TestCheckSuiteRequested(TestCase):
    event_type = CheckSuiteRequestedEvent

    # noinspection PyPep8Naming
    def setUp(self):
        self.client = app.test_client()

        default_branch = Mock(name="default_branch", protected=True)
        patch.object(Repository, "get_branch", return_value=default_branch).start()

        self.pull_request = Mock(
            spec=PullRequest,
            number=123,
            title="Pull Request Title",
            user=Mock(login=Config.BOT_NAME),
        )
        self.pull_request.get_commits().reversed = [Mock(commit=Mock(message="blank"))]
        patch.object(Repository, "get_pulls", return_value=[self.pull_request]).start()
        patch.object(Repository, "create_pull", return_value=self.pull_request).start()

    # noinspection PyPep8Naming
    def tearDown(self):
        patch.stopall()
        pull_request_helper.cache.clear()

    def assert_sub_run_calls(self, **kwargs):
        def get_final_state(sub_run_name):
            final_state = kwargs.get(f"final_{sub_run_name}")
            if isinstance(final_state, dict):
                return final_state
            elif final_state == "ignore":
                return None

            return {"title": final_state}

        def get_final_summary(state):
            if not state:
                return ""
            summary = [state["title"]]
            if s := state.get("summary"):
                summary.append(s)

            return "\n".join(summary)

        final_create_pull_request = get_final_state("create_pull_request")
        final_enable_auto_merge = get_final_state("enable_auto_merge")
        final_auto_update_pull_requests = get_final_state("auto_update_pull_requests")
        self.assert_check_run_start("Pull Request Manager", title="Initializing...")
        self.create_sub_runs(
            "Pull Request Manager", "Create Pull Request", "Enable auto-merge", "Auto Update Pull Requests"
        )

        if final_create_pull_request:
            if final_create_pull_request.pop("conclusion", None) != CheckRunConclusion.SKIPPED:
                self.assert_sub_run_call("Pull Request Manager", "Create Pull Request", title="Creating Pull Request")
            self.assert_sub_run_call("Pull Request Manager", "Create Pull Request", **final_create_pull_request)

        if final_enable_auto_merge:
            if final_enable_auto_merge.pop("conclusion", None) != CheckRunConclusion.SKIPPED:
                self.assert_sub_run_call("Pull Request Manager", "Enable auto-merge", title="Enabling auto-merge")
            self.assert_sub_run_call("Pull Request Manager", "Enable auto-merge", **final_enable_auto_merge)

        if final_auto_update_pull_requests:
            if final_auto_update_pull_requests.pop("conclusion", None) != CheckRunConclusion.SKIPPED:
                self.assert_sub_run_call(
                    "Pull Request Manager", "Auto Update Pull Requests", title="Updating Pull Requests"
                )
            self.assert_sub_run_call(
                "Pull Request Manager", "Auto Update Pull Requests", **final_auto_update_pull_requests
            )

        self.assert_check_run_final_state(
            "Pull Request Manager",
            title=kwargs.get("final_title", "Done"),
            summary=f"Create Pull Request: {get_final_summary(final_create_pull_request)}\n"
            f"Enable auto-merge: {get_final_summary(final_enable_auto_merge)}\n"
            f"Auto Update Pull Requests: {get_final_summary(final_auto_update_pull_requests)}",
            conclusion=kwargs.get("final_conclusion"),
        )

    def test_when_head_branch_is_not_default_branch(self):
        event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})

        event.repository.create_pull.assert_called_once_with(
            "default_branch",
            "feature_branch",
            title="feature_branch",
            body="Pull Request automatically created",
            draft=False,
        )
        self.pull_request.enable_automerge.assert_called_once_with(
            merge_method=Config.pull_request_manager.merge_method
        )
        self.pull_request.create_review.assert_not_called()

        self.assert_sub_run_calls(
            final_create_pull_request="Pull Request created",
            final_enable_auto_merge="Auto-merge enabled",
            final_auto_update_pull_requests="No Pull Requests Updated",
        )

    def test_when_a_pull_request_already_exists(self):
        with (
            patch.object(
                Repository,
                "create_pull",
                side_effect=self.create_github_exception(
                    "A pull request already exists for heitorpolidoro:feature_branch."
                ),
            ),
        ):
            event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})

            event.repository.create_pull.assert_called_once_with(
                "default_branch",
                "feature_branch",
                title="feature_branch",
                body="Pull Request automatically created",
                draft=False,
            )
            self.pull_request.enable_automerge.assert_called_once_with(
                merge_method=Config.pull_request_manager.merge_method
            )
            self.pull_request.create_review.assert_not_called()

        self.assert_sub_run_calls(
            final_create_pull_request="Pull Request already exists",
            final_enable_auto_merge="Auto-merge enabled",
            final_auto_update_pull_requests="No Pull Requests Updated",
        )

    def test_when_create_pull_request_is_disabled(self):
        with (
            patch.object(
                Config.pull_request_manager,
                "create_pull_request",
                False,
            ),
        ):
            event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})
            event.repository.create_pull.assert_not_called()
            self.pull_request.enable_automerge.assert_called_once_with(
                merge_method=Config.pull_request_manager.merge_method
            )
            self.pull_request.create_review.assert_not_called()
            self.assert_sub_run_calls(
                final_create_pull_request={"title": "Disabled", "conclusion": CheckRunConclusion.SKIPPED},
                final_enable_auto_merge="Auto-merge enabled",
                final_auto_update_pull_requests="No Pull Requests Updated",
            )

    def test_when_create_pull_request_is_disabled_and_there_is_no_pull_request(self):
        with (
            patch.object(
                Config.pull_request_manager,
                "create_pull_request",
                False,
            ),
            patch.object(Repository, "get_pulls", return_value=[]),
        ):
            event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})
            event.repository.create_pull.assert_not_called()
            self.pull_request.enable_automerge.assert_not_called()
            self.pull_request.create_review.assert_not_called()
            self.assert_sub_run_calls(
                final_create_pull_request={"title": "Disabled", "conclusion": CheckRunConclusion.SKIPPED},
                final_enable_auto_merge={
                    "title": "Enabling auto-merge failure",
                    "summary": "There is no Pull Request for the head branch feature_branch",
                },
                final_auto_update_pull_requests="No Pull Requests Updated",
                final_title="Enabling auto-merge failure",
                final_conclusion=CheckRunConclusion.FAILURE,
            )

    def test_when_create_pull_request_and_auto_merge_are_disabled(self):
        with (
            patch.object(
                Config.pull_request_manager,
                "create_pull_request",
                False,
            ),
            patch.object(
                Config.pull_request_manager,
                "enable_auto_merge",
                False,
            ),
        ):
            event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})
            event.repository.create_pull.assert_not_called()
            self.pull_request.enable_automerge.assert_not_called()
            self.pull_request.create_review.assert_not_called()

            self.assert_sub_run_calls(
                final_create_pull_request={"title": "Disabled", "conclusion": CheckRunConclusion.SKIPPED},
                final_enable_auto_merge={"title": "Disabled", "conclusion": CheckRunConclusion.SKIPPED},
                final_auto_update_pull_requests="No Pull Requests Updated",
            )

    def test_when_head_branch_is_default_branch(self):
        event = self.deliver(self.event_type, check_suite={"head_branch": "default_branch"})
        event.repository.create_pull.assert_not_called()
        self.pull_request.enable_automerge.assert_not_called()
        self.pull_request.create_review.assert_not_called()
        self.assert_sub_run_calls(
            final_create_pull_request={
                "title": IGNORING_TITLE,
                "conclusion": CheckRunConclusion.SKIPPED,
            },
            final_enable_auto_merge={
                "title": IGNORING_TITLE,
                "conclusion": CheckRunConclusion.SKIPPED,
            },
            final_auto_update_pull_requests="No Pull Requests Updated",
        )

    def test_when_an_error_happens_when_creating_the_pull_request(self):
        with (patch.object(Repository, "create_pull", side_effect=self.create_github_exception("Any Github Error")),):
            event = self.deliver(
                self.event_type,
                check_suite={"head_branch": "feature_branch"},
            )
            event.repository.create_pull.assert_called_once_with(
                "default_branch",
                "feature_branch",
                title="feature_branch",
                body="Pull Request automatically created",
                draft=False,
            )
            self.pull_request.enable_automerge.assert_not_called()

            self.assert_sub_run_calls(
                final_create_pull_request={
                    "title": "Pull Request creation failure",
                    "summary": "Any Github Error",
                },
                final_enable_auto_merge="ignore",
                final_auto_update_pull_requests="No Pull Requests Updated",
                final_title="Pull Request creation failure",
                final_conclusion=CheckRunConclusion.FAILURE,
            )

    def test_when_an_error_happens_when_enabling_auto_merge(self):
        with (
            patch.object(
                self.pull_request, "enable_automerge", side_effect=self.create_github_exception("Any Github Error")
            ),
        ):
            event = self.deliver(
                self.event_type,
                check_suite={"head_branch": "feature_branch"},
            )
            event.repository.create_pull.assert_called_once_with(
                "default_branch",
                "feature_branch",
                title="feature_branch",
                body="Pull Request automatically created",
                draft=False,
            )
            self.pull_request.enable_automerge.assert_called_once_with(
                merge_method=Config.pull_request_manager.merge_method
            )

        self.assert_sub_run_calls(
            final_create_pull_request="Pull Request created",
            final_enable_auto_merge={"title": "Enabling auto-merge failure", "summary": "Any Github Error"},
            final_auto_update_pull_requests="No Pull Requests Updated",
            final_title="Enabling auto-merge failure",
            final_conclusion=CheckRunConclusion.FAILURE,
        )

    def test_when_an_the_default_branch_is_not_protected(self):
        with (patch.object(Repository, "get_branch", return_value=Mock(protected=False)),):
            event = self.deliver(
                self.event_type,
                check_suite={"head_branch": "feature_branch"},
            )
            event.repository.create_pull.assert_called_once_with(
                "default_branch",
                "feature_branch",
                title="feature_branch",
                body="Pull Request automatically created",
                draft=False,
            )
            self.pull_request.enable_automerge.assert_not_called()

        self.assert_sub_run_calls(
            final_create_pull_request="Pull Request created",
            final_enable_auto_merge={
                "title": "Cannot enable auto-merge in a repository with no protected branch.",
                "summary": "Check [Enabling auto-merge](https://docs.github.com/en/pull-requests/"
                "collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/"
                "automatically-merging-a-pull-request#enabling-auto-merge) for more information",
            },
            final_auto_update_pull_requests="No Pull Requests Updated",
            final_title="Cannot enable auto-merge in a repository with no protected branch.",
            final_conclusion=CheckRunConclusion.FAILURE,
        )

    def test_update_pull_requests(self):
        ahead_pull_request = Mock(
            spec=PullRequest,
            number=1,
            title="Ahead Pull Request Title",
            mergeable_state="ahead",
        )
        behind_pull_request = Mock(
            spec=PullRequest,
            number=2,
            title="Behind Pull Request Title",
            mergeable_state="behind",
        )

        with patch.object(Repository, "get_pulls", return_value=[ahead_pull_request, behind_pull_request]):
            event = self.deliver(self.event_type, check_suite={"head_branch": "default_branch"})
            event.repository.create_pull.assert_not_called()
            self.pull_request.enable_automerge.assert_not_called()
            self.pull_request.create_review.assert_not_called()
            self.assert_sub_run_calls(
                final_create_pull_request={
                    "title": IGNORING_TITLE,
                    "conclusion": CheckRunConclusion.SKIPPED,
                },
                final_enable_auto_merge={
                    "title": IGNORING_TITLE,
                    "conclusion": CheckRunConclusion.SKIPPED,
                },
                final_auto_update_pull_requests={
                    "title": "Pull Requests Updated",
                    "summary": "#2 Behind Pull Request Title",
                },
            )

    def test_auto_update_is_disabled(self):
        with patch.object(
            Config.pull_request_manager,
            "auto_update",
            False,
        ):
            event = self.deliver(self.event_type, check_suite={"head_branch": "default_branch"})
            event.repository.create_pull.assert_not_called()
            self.pull_request.enable_automerge.assert_not_called()
            self.pull_request.create_review.assert_not_called()
            self.assert_sub_run_calls(
                final_create_pull_request={
                    "title": IGNORING_TITLE,
                    "conclusion": CheckRunConclusion.SKIPPED,
                },
                final_enable_auto_merge={
                    "title": IGNORING_TITLE,
                    "conclusion": CheckRunConclusion.SKIPPED,
                },
                final_auto_update_pull_requests={"title": "Disabled", "conclusion": CheckRunConclusion.SKIPPED},
                final_conclusion=CheckRunConclusion.SKIPPED,
                final_title="Skipped"
            )


class TestCheckSuiteRerequested(TestCheckSuiteRequested):
    event_type = CheckSuiteRerequestedEvent
