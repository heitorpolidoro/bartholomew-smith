from unittest.mock import ANY, Mock, call, patch

from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config
from githubapp.event_check_run import CheckRunConclusion, CheckRunStatus
from githubapp.events import CheckSuiteRequestedEvent
from githubapp.test_helper import TestCase

from app import app
from src.helpers import pull_request_helper

IGNORING_TITLE = "In the default branch 'default_branch', ignoring."

VERSION_FILE = """
__version__ = $version

"""


class TestCheckSuiteRequested(TestCase):
    event_type = CheckSuiteRequestedEvent
    client = app.test_client()

    def setup_method(self, method):
        super().setup_method(method)

        def repository_get_branch(self, branch_name):
            if branch_name == self.default_branch:
                return Mock(name=branch_name, protected=True)
            return Mock(name=branch_name)

        patch.object(Repository, "get_branch", repository_get_branch).start()
        # self.mock_repository_get_content(
        #     "heitorpolidoro/bartholomew-smith", ".bartholomew.yaml", "default_branch", None
        # )
        # self.mock_pull_request("heitorpolidoro/bartholomew-smith")

    def teardown_method(self, method):
        super().teardown_method(method)
        patch.stopall()
        pull_request_helper.cache.clear()

    #     def setUp(self):
    #         default_branch = Mock(name="default_branch", protected=True)
    #         patch.object(Repository, "get_branch", return_value=default_branch).start()
    #
    #         self.pull_request = Mock(
    #             spec=PullRequest,
    #             number=123,
    #             title="Pull Request Title",
    #             user=Mock(login=Config.BOT_NAME),
    #         )
    #         self.pull_request.get_commits().reversed = [Mock(commit=Mock(message="blank"))]
    #         patch.object(Repository, "get_pulls", return_value=[self.pull_request]).start()
    #         patch.object(Repository, "create_pull", return_value=self.pull_request).start()
    #         patch.object(Repository, "create_git_release").start()
    #         # TODO better way to test the managers separately
    #         patch.object(Config.release_manager, "enabled", False).start()
    #
    @staticmethod
    def setup_config():
        Config.release_manager.enabled = False
        Config.issue_manager.enabled = False
        Config.pull_request_manager.set_values(
            enabled=True,
            create_pull_request=True,
            link_issue=True,
            enable_auto_merge=True,
            merge_method="SQUASH",
            auto_approve=False,
            auto_approve_logins=[],
            auto_update=True,
        )

    def test_when_head_branch_is_not_default_branch(self, event_type):
        """
        Create the Pull Request
        Enable auto merge
        Don't update any Pull Request
        Don't approve
        """
        pull_request = Mock(spec=PullRequest)
        with (
            patch.object(Repository, "create_pull", return_value=pull_request),
            patch.object(Repository, "get_pulls", return_value=[]),
        ):
            event = self.deliver(
                self.event_type, check_suite={"head_branch": "feature_branch"}
            )

            event.repository.create_pull.assert_called_once_with(
                "default_branch",
                "feature_branch",
                title="feature_branch",
                body="Pull Request automatically created",
                draft=False,
            )
            pull_request.enable_automerge.assert_called_once_with(
                merge_method=Config.pull_request_manager.merge_method
            )

            self.assert_check_run_calls(
                "Pull Request Manager",
                [call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS)],
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Create Pull Request",
                    [
                        call(
                            title="Creating Pull Request",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="Pull Request created",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Enable auto-merge",
                    [
                        call(
                            title="Enabling auto-merge",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="Auto-merge enabled",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Auto Update Pull Requests",
                    [
                        call(
                            title="Updating Pull Requests",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="No Pull Requests Updated",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
            )
            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Done",
                summary="Create Pull Request: Pull Request created\n"
                "Enable auto-merge: Auto-merge enabled\n"
                "Auto Update Pull Requests: No Pull Requests Updated",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()

    def test_when_head_branch_is_the_default_branch(self, event_type):
        """
        Don't create the Pull Request
        Don't enable auto merge
        Update the Pull Requests
        """
        pull_requests = [
            Mock(
                spec=PullRequest, mergeable_state="behind", number=1, title="PR Title 1"
            ),
            Mock(
                spec=PullRequest,
                mergeable_state="not_behind",
                number=2,
                title="PR Title 2",
            ),
            Mock(
                spec=PullRequest, mergeable_state="behind", number=3, title="PR Title 3"
            ),
        ]
        with (
            patch.object(Repository, "get_pulls", return_value=pull_requests),
        ):
            event = self.deliver(
                self.event_type, check_suite={"head_branch": "default_branch"}
            )

            event.repository.create_pull.assert_not_called()
            for pull_request in pull_requests:
                pull_request.enable_automerge.assert_not_called()
                if pull_request.mergeable_state == "behind":
                    pull_request.update_branch.assert_called_once()
                else:
                    pull_request.update_branch.assert_not_called()

            self.assert_check_run_calls(
                "Pull Request Manager",
                [call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS)],
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Create Pull Request",
                    [
                        call(
                            title="In the default branch 'default_branch', ignoring.",
                            conclusion=CheckRunConclusion.SKIPPED,
                            update_check_run=False,
                        ),
                    ],
                ),
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Enable auto-merge",
                    [
                        call(
                            title="In the default branch 'default_branch', ignoring.",
                            conclusion=CheckRunConclusion.SKIPPED,
                            update_check_run=False,
                        ),
                    ],
                ),
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Auto Update Pull Requests",
                    [
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
                ),
            )
            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Done",
                summary="Create Pull Request: In the default branch 'default_branch', ignoring.\n"
                "Enable auto-merge: In the default branch 'default_branch', ignoring.\n"
                "Auto Update Pull Requests: Pull Requests Updated\n"
                "#1 PR Title 1\n"
                "#3 PR Title 3",
                text=None,
                status=None,
            )

            self.assert_all_check_runs_calls_asserted()

    def test_when_a_pull_request_already_exists(self, event_type):
        """
        Pull Request already exists
        Enable auto merge
        Don't update any Pull Request
        """
        pull_request = Mock(spec=PullRequest)
        with (
            patch.object(
                Repository,
                "create_pull",
                side_effect=self.create_github_exception(
                    "A pull request already exists for heitorpolidoro:feature_branch."
                ),
            ),
            patch.object(Repository, "get_pulls", return_value=[pull_request]),
        ):
            event = self.deliver(
                self.event_type, check_suite={"head_branch": "feature_branch"}
            )

            event.repository.create_pull.assert_called_once_with(
                "default_branch",
                "feature_branch",
                title="feature_branch",
                body="Pull Request automatically created",
                draft=False,
            )
            pull_request.enable_automerge.assert_called_once_with(
                merge_method=Config.pull_request_manager.merge_method
            )
            pull_request.create_review.assert_not_called()

            self.assert_check_run_calls(
                "Pull Request Manager",
                [call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS)],
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Create Pull Request",
                    [
                        call(
                            title="Creating Pull Request",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="Pull Request already exists",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Enable auto-merge",
                    [
                        call(
                            title="Enabling auto-merge",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="Auto-merge enabled",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Auto Update Pull Requests",
                    [
                        call(
                            title="Updating Pull Requests",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="No Pull Requests Updated",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
            )
            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Done",
                summary="Create Pull Request: Pull Request already exists\n"
                "Enable auto-merge: Auto-merge enabled\n"
                "Auto Update Pull Requests: No Pull Requests Updated",
                text=None,
                status=None,
            )

    def test_when_another_github_exception_in_pull_request_creation(self, event_type):
        """
        Pull Request already exists
        Enable auto merge
        Don't update any Pull Request
        """
        pull_request = Mock(spec=PullRequest)
        with (
            patch.object(
                Repository,
                "create_pull",
                side_effect=self.create_github_exception("Other GithubException."),
            ),
            patch.object(Repository, "get_pulls", return_value=[pull_request]),
        ):
            event = self.deliver(
                self.event_type, check_suite={"head_branch": "feature_branch"}
            )

            event.repository.create_pull.assert_called_once_with(
                "default_branch",
                "feature_branch",
                title="feature_branch",
                body="Pull Request automatically created",
                draft=False,
            )
            pull_request.enable_automerge.assert_not_called()
            pull_request.create_review.assert_not_called()

            self.assert_check_run_calls(
                "Pull Request Manager",
                [call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS)],
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Create Pull Request",
                    [
                        call(
                            title="Creating Pull Request",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="Pull Request creation failure",
                            summary="Other GithubException.",
                            conclusion=CheckRunConclusion.FAILURE,
                        ),
                    ],
                ),
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Enable auto-merge",
                    [
                        call(
                            title="Cancelled",
                            conclusion=CheckRunConclusion.CANCELLED,
                            update_check_run=False,
                        ),
                    ],
                ),
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Auto Update Pull Requests",
                    [
                        call(
                            title="Updating Pull Requests",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="No Pull Requests Updated",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
            )
            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.FAILURE,
                title="Pull Request creation failure",
                summary="Create Pull Request: Pull Request creation failure\n"
                "Other GithubException.\n"
                "Enable auto-merge: Cancelled\n"
                "Auto Update Pull Requests: No Pull Requests Updated",
                text=ANY,
                status=None,
            )

    def test_when_there_is_an_error_on_creating_the_pull_request(self, event_type):
        """
        Error to create Pull Request
        Cancel Enable auto merge
        Update any Pull Request
        """
        pull_request = Mock(
            spec=PullRequest, mergeable_state="behind", number=1, title="PR Title 1"
        )
        with (
            patch.object(
                Repository,
                "create_pull",
                side_effect=Exception("Other Error"),
            ),
            patch.object(Repository, "get_pulls", return_value=[pull_request]),
        ):
            event = self.deliver(
                self.event_type, check_suite={"head_branch": "feature_branch"}
            )

            event.repository.create_pull.assert_called_once_with(
                "default_branch",
                "feature_branch",
                title="feature_branch",
                body="Pull Request automatically created",
                draft=False,
            )
            pull_request.enable_automerge.assert_not_called()
            pull_request.update_branch.assert_called_once()
            pull_request.create_review.assert_not_called()

            self.assert_check_run_calls(
                "Pull Request Manager",
                [call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS)],
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Create Pull Request",
                    [
                        call(
                            title="Creating Pull Request",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="Pull Request creation failure",
                            summary="Other Error",
                            conclusion=CheckRunConclusion.FAILURE,
                        ),
                    ],
                ),
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Enable auto-merge",
                    [
                        call(
                            title="Cancelled",
                            conclusion=CheckRunConclusion.CANCELLED,
                            update_check_run=False,
                        ),
                    ],
                ),
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Auto Update Pull Requests",
                    [
                        call(
                            title="Updating Pull Requests",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="Pull Requests Updated",
                            summary="#1 PR Title 1",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
            )
            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.FAILURE,
                title="Pull Request creation failure",
                summary="Create Pull Request: Pull Request creation failure\n"
                "Other Error\n"
                "Enable auto-merge: Cancelled\n"
                "Auto Update Pull Requests: Pull Requests Updated\n"
                "#1 PR Title 1",
                text=ANY,
                status=None,
            )

    def test_when_create_pull_request_is_disabled(self, event_type):
        """
        Don't create the Pull Request
        Enable auto merge
        Don't update any Pull Request
        """
        pull_request = Mock(spec=PullRequest)
        with (
            patch.object(
                Config.pull_request_manager,
                "create_pull_request",
                False,
            ),
            patch.object(Repository, "get_pulls", return_value=[pull_request]),
        ):
            event = self.deliver(
                self.event_type, check_suite={"head_branch": "feature_branch"}
            )
            event.repository.create_pull.assert_not_called()
            pull_request.enable_automerge.assert_called_once_with(
                merge_method=Config.pull_request_manager.merge_method
            )
            pull_request.create_review.assert_not_called()

            self.assert_check_run_calls(
                "Pull Request Manager",
                [call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS)],
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Enable auto-merge",
                    [
                        call(
                            title="Enabling auto-merge",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="Auto-merge enabled",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Auto Update Pull Requests",
                    [
                        call(
                            title="Updating Pull Requests",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="No Pull Requests Updated",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
            )
            self.assert_last_check_run_call(
                "Pull Request Manager",
                conclusion=CheckRunConclusion.SUCCESS,
                title="Done",
                summary="Create Pull Request: Disabled\n"
                "Enable auto-merge: Auto-merge enabled\n"
                "Auto Update Pull Requests: No Pull Requests Updated",
                text=None,
                status=None,
            )

    #
    def test_when_enable_auto_merge_is_disabled(self, event_type):
        """
        Don't create the Pull Request
        Don't enable auto merge
        Don't update any Pull Request
        """
        pull_request = Mock(spec=PullRequest)
        with (
            patch.object(
                Config.pull_request_manager,
                "enable_auto_merge",
                False,
            ),
            patch.object(
                Config.pull_request_manager,
                "create_pull_request",
                False,
            ),
            patch.object(Repository, "get_pulls", return_value=[pull_request]),
        ):
            event = self.deliver(
                self.event_type, check_suite={"head_branch": "feature_branch"}
            )
            event.repository.create_pull.assert_not_called()
            pull_request.enable_automerge.assert_not_called()
            pull_request.create_review.assert_not_called()

            self.assert_check_run_calls(
                "Pull Request Manager",
                [call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS)],
            )
            (
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Enable auto-merge",
                    [
                        call(title="Disabled", conclusion=CheckRunConclusion.SKIPPED),
                    ],
                ),
                self.assert_subrun_calls(
                    "Pull Request Manager",
                    "Auto Update Pull Requests",
                    [
                        call(
                            title="Updating Pull Requests",
                            status=CheckRunStatus.IN_PROGRESS,
                        ),
                        call(
                            title="No Pull Requests Updated",
                            conclusion=CheckRunConclusion.SUCCESS,
                        ),
                    ],
                ),
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


#
#     def test_when_create_pull_request_is_disabled_and_there_is_no_pull_request(self, event_type):
#         with (
#             patch.object(
#                 Config.pull_request_manager,
#                 "create_pull_request",
#                 False,
#             ),
#             patch.object(Repository, "get_pulls", return_value=[]),
#         ):
#             event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})
#             event.repository.create_pull.assert_not_called()
#             self.pull_request.enable_automerge.assert_not_called()
#             self.pull_request.create_review.assert_not_called()
#             self.assert_sub_run_calls(
#                 "Pull Request Manager",
#                 final_create_pull_request={
#                     "title": "Disabled",
#                     "conclusion": CheckRunConclusion.SKIPPED,
#                 },
#                 final_enable_auto_merge={
#                     "title": "Enabling auto-merge failure",
#                     "summary": "There is no Pull Request for the head branch feature_branch",
#                 },
#                 final_auto_update_pull_requests="No Pull Requests Updated",
#                 final_title="Enabling auto-merge failure",
#                 final_conclusion=CheckRunConclusion.FAILURE,
#             )
#             self.assert_no_check_run("Releaser")
#
#     def test_when_create_pull_request_and_enable_auto_merge_are_disabled(self, event_type):
#         with (
#             patch.object(
#                 Config.pull_request_manager,
#                 "create_pull_request",
#                 False,
#             ),
#             patch.object(
#                 Config.pull_request_manager,
#                 "enable_auto_merge",
#                 False,
#             ),
#         ):
#             event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})
#             event.repository.create_pull.assert_not_called()
#             self.pull_request.enable_automerge.assert_not_called()
#             self.pull_request.create_review.assert_not_called()
#
#             self.assert_sub_run_calls(
#                 "Pull Request Manager",
#                 final_create_pull_request={
#                     "title": "Disabled",
#                     "conclusion": CheckRunConclusion.SKIPPED,
#                 },
#                 final_enable_auto_merge={
#                     "title": "Disabled",
#                     "conclusion": CheckRunConclusion.SKIPPED,
#                 },
#                 final_auto_update_pull_requests="No Pull Requests Updated",
#             )
#             self.assert_no_check_run("Releaser")
#
#     def test_when_head_branch_is_default_branch(self, event_type):
#         event = self.deliver(self.event_type, check_suite={"head_branch": "default_branch"})
#         event.repository.create_pull.assert_not_called()
#         self.pull_request.enable_automerge.assert_not_called()
#         self.pull_request.create_review.assert_not_called()
#         self.assert_sub_run_calls(
#             "Pull Request Manager",
#             final_create_pull_request={
#                 "title": IGNORING_TITLE,
#                 "conclusion": CheckRunConclusion.SKIPPED,
#             },
#             final_enable_auto_merge={
#                 "title": IGNORING_TITLE,
#                 "conclusion": CheckRunConclusion.SKIPPED,
#             },
#             final_auto_update_pull_requests="No Pull Requests Updated",
#         )
#         self.assert_no_check_run("Releaser")
#
#     def test_when_an_error_happens_when_creating_the_pull_request(self, event_type):
#         with (
#             patch.object(
#                 Repository,
#                 "create_pull",
#                 side_effect=self.create_github_exception("Any Github Error"),
#             ),
#         ):
#             event = self.deliver(
#                 self.event_type,
#                 check_suite={"head_branch": "feature_branch"},
#             )
#             event.repository.create_pull.assert_called_once_with(
#                 "default_branch",
#                 "feature_branch",
#                 title="feature_branch",
#                 body="Pull Request automatically created",
#                 draft=False,
#             )
#             self.pull_request.enable_automerge.assert_not_called()
#
#             self.assert_sub_run_calls(
#                 "Pull Request Manager",
#                 final_create_pull_request={
#                     "title": "Pull Request creation failure",
#                     "summary": "Any Github Error",
#                 },
#                 final_enable_auto_merge="ignore",
#                 final_auto_update_pull_requests="No Pull Requests Updated",
#                 final_title="Pull Request creation failure",
#                 final_conclusion=CheckRunConclusion.FAILURE,
#             )
#             self.assert_no_check_run("Releaser")
#
#     def test_when_an_error_happens_when_enabling_enable_auto_merge(self, event_type):
#         with (
#             patch.object(
#                 self.pull_request,
#                 "enable_automerge",
#                 side_effect=self.create_github_exception("Any Github Error"),
#             ),
#         ):
#             event = self.deliver(
#                 self.event_type,
#                 check_suite={"head_branch": "feature_branch"},
#             )
#             event.repository.create_pull.assert_called_once_with(
#                 "default_branch",
#                 "feature_branch",
#                 title="feature_branch",
#                 body="Pull Request automatically created",
#                 draft=False,
#             )
#             self.pull_request.enable_automerge.assert_called_once_with(
#                 merge_method=Config.pull_request_manager.merge_method
#             )
#
#             self.assert_sub_run_calls(
#                 "Pull Request Manager",
#                 final_create_pull_request="Pull Request created",
#                 final_enable_auto_merge={
#                     "title": "Enabling auto-merge failure",
#                     "summary": "Any Github Error",
#                 },
#                 final_auto_update_pull_requests="No Pull Requests Updated",
#                 final_title="Enabling auto-merge failure",
#                 final_conclusion=CheckRunConclusion.FAILURE,
#             )
#             self.assert_no_check_run("Releaser")
#
#     def test_when_an_the_default_branch_is_not_protected(self, event_type):
#         with (patch.object(Repository, "get_branch", return_value=Mock(protected=False)),):
#             event = self.deliver(
#                 self.event_type,
#                 check_suite={"head_branch": "feature_branch"},
#             )
#             event.repository.create_pull.assert_called_once_with(
#                 "default_branch",
#                 "feature_branch",
#                 title="feature_branch",
#                 body="Pull Request automatically created",
#                 draft=False,
#             )
#             self.pull_request.enable_automerge.assert_not_called()
#
#             self.assert_sub_run_calls(
#                 "Pull Request Manager",
#                 final_create_pull_request="Pull Request created",
#                 final_enable_auto_merge={
#                     "title": "Cannot enable auto-merge in a repository with no protected branch.",
#                     "summary": "Check [Enabling auto-merge](https://docs.github.com/en/pull-requests/"
#                     "collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/"
#                     "automatically-merging-a-pull-request#enabling-auto-merge) for more information",
#                 },
#                 final_auto_update_pull_requests="No Pull Requests Updated",
#                 final_title="Cannot enable auto-merge in a repository with no protected branch.",
#                 final_conclusion=CheckRunConclusion.FAILURE,
#             )
#             self.assert_no_check_run("Releaser")
#
#     def test_update_pull_requests(self, event_type):
#         ahead_pull_request = Mock(
#             spec=PullRequest,
#             number=1,
#             title="Ahead Pull Request Title",
#             mergeable_state="ahead",
#         )
#         dont_need_to_update_pull_request = Mock(
#             spec=PullRequest,
#             number=2,
#             title="Behind Pull Request Title",
#             mergeable_state="behind",
#         )
#         dont_need_to_update_pull_request.update_branch.return_value = False
#         need_to_update_pull_request1 = Mock(
#             spec=PullRequest,
#             number=3,
#             title="Behind Pull Request Title 2",
#             mergeable_state="behind",
#         )
#         need_to_update_pull_request1.update_branch.return_value = True
#         need_to_update_pull_request2 = Mock(
#             spec=PullRequest,
#             number=4,
#             title="Behind Pull Request Title 3",
#             mergeable_state="behind",
#         )
#         need_to_update_pull_request2.update_branch.return_value = True
#         behind_pull_requests = [
#             dont_need_to_update_pull_request,
#             need_to_update_pull_request1,
#             need_to_update_pull_request2,
#         ]
#
#         with patch.object(
#             Repository,
#             "get_pulls",
#             return_value=[ahead_pull_request] + behind_pull_requests,
#         ):
#             event = self.deliver(self.event_type, check_suite={"head_branch": "default_branch"})
#             event.repository.create_pull.assert_not_called()
#             self.pull_request.enable_automerge.assert_not_called()
#             self.pull_request.create_review.assert_not_called()
#             for behind_pull_request in behind_pull_requests:
#                 behind_pull_request.update_branch.assert_called_once_with()
#             self.assert_sub_run_calls(
#                 "Pull Request Manager",
#                 final_create_pull_request={
#                     "title": IGNORING_TITLE,
#                     "conclusion": CheckRunConclusion.SKIPPED,
#                 },
#                 final_enable_auto_merge={
#                     "title": IGNORING_TITLE,
#                     "conclusion": CheckRunConclusion.SKIPPED,
#                 },
#                 final_auto_update_pull_requests={
#                     "title": "Pull Requests Updated",
#                     "summary": "#3 Behind Pull Request Title 2\n#4 Behind Pull Request Title 3",
#                 },
#             )
#             self.assert_no_check_run("Releaser")
#
#     def test_auto_update_is_disabled(self, event_type):
#         with patch.object(
#             Config.pull_request_manager,
#             "auto_update",
#             False,
#         ):
#             event = self.deliver(self.event_type, check_suite={"head_branch": "default_branch"})
#             event.repository.create_pull.assert_not_called()
#             self.pull_request.enable_automerge.assert_not_called()
#             self.pull_request.create_review.assert_not_called()
#             self.assert_sub_run_calls(
#                 "Pull Request Manager",
#                 final_create_pull_request={
#                     "title": IGNORING_TITLE,
#                     "conclusion": CheckRunConclusion.SKIPPED,
#                 },
#                 final_enable_auto_merge={
#                     "title": IGNORING_TITLE,
#                     "conclusion": CheckRunConclusion.SKIPPED,
#                 },
#                 final_auto_update_pull_requests={
#                     "title": "Disabled",
#                     "conclusion": CheckRunConclusion.SKIPPED,
#                 },
#                 final_conclusion=CheckRunConclusion.SKIPPED,
#                 final_title="Skipped",
#             )
#             self.assert_no_check_run("Releaser")
#
#     def test_release_manager_with_no_command(self, event_type):
#         with (
#             patch.object(Config.release_manager, "enabled", True),
#             patch.object(Config.pull_request_manager, "enabled", False),
#         ):
#             event = self.deliver(self.event_type)
#             event.repository.create_git_release.assert_not_called()
#             self.assert_no_check_run("Pull Request Manager")
#             self.assert_check_run_progression(
#                 "Releaser",
#                 [
#                     call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
#                     call(title="Checking for release command..."),
#                     call(
#                         title="No release command found",
#                         conclusion=CheckRunConclusion.SUCCESS,
#                     ),
#                 ],
#             )
#
#     def test_release_manager_with_command(self, event_type):
#         compare = Mock()
#         compare.commits.reversed = [Mock(commit=Mock(message="[release:1.2.3]"))]
#         with (
#             patch.object(Config.release_manager, "enabled", True),
#             patch.object(Config.pull_request_manager, "enabled", False),
#             patch.object(Repository, "compare", return_value=compare),
#         ):
#             event = self.deliver(self.event_type)
#             event.repository.create_git_release.assert_called_once_with(tag="1.2.3", generate_release_notes=True)
#             self.assert_no_check_run("Pull Request Manager")
#             self.assert_check_run_progression(
#                 "Releaser",
#                 [
#                     call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
#                     call(title="Checking for release command..."),
#                     call(title="Releasing 1.2.3..."),
#                     call(title="1.2.3 released ✅", conclusion=CheckRunConclusion.SUCCESS),
#                 ],
#             )
#
#     def test_release_manager_get_last_command(self, event_type):
#         compare = Mock()
#         compare.commits.reversed = [
#             Mock(commit=Mock(message="blebleble")),
#             Mock(commit=Mock(message="[release:3.2.1]")),
#             Mock(commit=Mock(message="blablabla")),
#             Mock(commit=Mock(message="[release:1.2.3]")),
#         ]
#         with (
#             patch.object(Config.release_manager, "enabled", True),
#             patch.object(Config.pull_request_manager, "enabled", False),
#             patch.object(Repository, "compare", return_value=compare),
#         ):
#             event = self.deliver(self.event_type)
#             event.repository.create_git_release.assert_called_once_with(tag="3.2.1", generate_release_notes=True)
#             self.assert_no_check_run("Pull Request Manager")
#             self.assert_check_run_progression(
#                 "Releaser",
#                 [
#                     call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
#                     call(title="Checking for release command..."),
#                     call(title="Releasing 3.2.1..."),
#                     call(title="3.2.1 released ✅", conclusion=CheckRunConclusion.SUCCESS),
#                 ],
#             )
#
#     def test_release_manager_with_relative_release(self, event_type):
#         compare = Mock()
#         compare.commits.reversed = [Mock(commit=Mock(message="[release:minor]"))]
#         with (
#             patch.object(Config.release_manager, "enabled", True),
#             patch.object(Config.pull_request_manager, "enabled", False),
#             patch.object(Repository, "compare", return_value=compare),
#             patch.object(Repository, "get_latest_release", return_value=Mock(tag_name="1.2.3")),
#         ):
#             event = self.deliver(self.event_type)
#             event.repository.create_git_release.assert_called_once_with(tag="1.3.0", generate_release_notes=True)
#             self.assert_no_check_run("Pull Request Manager")
#             self.assert_check_run_progression(
#                 "Releaser",
#                 [
#                     call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
#                     call(title="Checking for release command..."),
#                     call(title="Releasing 1.3.0..."),
#                     call(title="1.3.0 released ✅", conclusion=CheckRunConclusion.SUCCESS),
#                 ],
#             )
#
#     def test_release_manager_with_invalid_release(self, event_type):
#         compare = Mock()
#         compare.commits.reversed = [Mock(commit=Mock(message="[release:3.in.valid]"))]
#         with (
#             patch.object(Config.release_manager, "enabled", True),
#             patch.object(Config.pull_request_manager, "enabled", False),
#             patch.object(Repository, "compare", return_value=compare),
#             patch.object(Repository, "get_latest_release", return_value=Mock(tag_name="1.2.3")),
#         ):
#             event = self.deliver(self.event_type)
#             event.repository.create_git_release.assert_not_called()
#             self.assert_no_check_run("Pull Request Manager")
#             self.assert_check_run_progression(
#                 "Releaser",
#                 [
#                     call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
#                     call(title="Checking for release command..."),
#                     call(
#                         title="Invalid release 3.in.valid",
#                         summary="Invalid release ❌",
#                         conclusion=CheckRunConclusion.FAILURE,
#                     ),
#                 ],
#             )
#
#     def test_release_manager_with_command_in_feature_branch(self, event_type):
#         self.pull_request.get_commits().reversed = [Mock(commit=Mock(message="[release:1.2.3]"))]
#         with (
#             patch.object(Config.release_manager, "enabled", True),
#             patch.object(Config.pull_request_manager, "enabled", False),
#         ):
#             event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})
#             event.repository.create_git_release.assert_not_called()
#             self.assert_no_check_run("Pull Request Manager")
#             self.assert_check_run_progression(
#                 "Releaser",
#                 [
#                     call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
#                     call(title="Checking for release command..."),
#                     call(
#                         title="Ready to release 1.2.3",
#                         summary="Release command found ✅",
#                         conclusion=CheckRunConclusion.SUCCESS,
#                     ),
#                 ],
#             )
#
#     def test_release_manager_with_no_pull_request_in_feature_branch(self, event_type):
#         with (
#             patch.object(Config.release_manager, "enabled", True),
#             patch.object(Config.pull_request_manager, "enabled", False),
#             patch.object(Repository, "get_pulls", return_value=[]),
#         ):
#             event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})
#             event.repository.create_git_release.assert_not_called()
#             self.assert_no_check_run("Pull Request Manager")
#             self.assert_check_run_progression(
#                 "Releaser",
#                 [
#                     call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
#                     call(
#                         title="No Pull Request found",
#                         conclusion=CheckRunConclusion.SUCCESS,
#                     ),
#                 ],
#             )
#
#     def test_update_in_file(self, event_type):
#         self.pull_request.get_commits().reversed = [Mock(commit=Mock(message="[release:1.2.3]"))]
#         with (
#             patch.object(Config.release_manager, "enabled", True),
#             patch.object(Config.pull_request_manager, "enabled", False),
#             patch.object(
#                 Config.release_manager,
#                 "update_in_file",
#                 {"file_path": "src/__init__.py", "pattern": "__version__ = $version"},
#             ),
#             patch.object(Repository, "get_contents", return_value=Mock(decoded_content=VERSION_FILE)),
#             patch.object(Repository, "update_file") as update_file,
#         ):
#             event = self.deliver(self.event_type, check_suite={"head_branch": "feature_branch"})
#             update_file.assert_called_once_with(
#                 "src/__init__.py",
#                 "Updating file 'src/__init__.py' for release",
#                 Template(VERSION_FILE).substitute(version="1.2.3"),
#                 event.check_suite.head_sha,
#                 branch="feature_branch",
#             )
#
#
# class TestCheckSuiteRerequested(TestCheckSuiteRequested):  # skipcq: PTC-W0046
#     event_type = CheckSuiteRerequestedEvent
#
#


# def test_get_title_and_body_from_issue_without_issue_in_branch(repository_mock):
#     assert get_title_and_body_from_issue(repository_mock, "feature_branch") == ("", "")
#
#
# def test_get_title_and_body_from_issue_when_it_is_disabled(repository_mock):
#     with patch.object(
#         Config.pull_request_manager,
#         "link_issue",
#         False,
#     ):
#         assert get_title_and_body_from_issue(repository_mock, "issue-42") == ("", "")
#
#
# def test_get_title_and_body_from_issue_with_issue_in_branch(repository_mock):
#     with patch.object(repository_mock, "get_issue", return_value=Mock(title="Title", body="Body")):
#         assert get_title_and_body_from_issue(repository_mock, "issue-42") == (
#             "Title",
#             """### [Title](https://github.com/heitorpolidoro/bartholomew-smith/issues/42)
#
# Body
#
# Closes #42
#
# """,
#         )
#
#
# def test_auto_approve():
#     auto_approve()
#
#
# def test_auto_approve_when_enabled(repository_mock):
#     pull_request = Mock()
#     with (
#         patch.object(
#             Config.pull_request_manager,
#             "auto_approve",
#             True,
#         ),
#         patch.object(
#             Config,
#             "AUTO_APPROVE_PAT",
#             "AUTOAPPROVEPAT",
#         ),
#         patch.object(repository_mock, "get_pulls", return_value=[pull_request]),
#         patch("src.managers.pull_request_manager.pull_request_helper") as pull_request_helper,
#     ):
#         auto_approve(repository_mock, "branch")
#         pull_request_helper.approve.assert_called_once_with(Config.AUTO_APPROVE_PAT, repository_mock, pull_request)
