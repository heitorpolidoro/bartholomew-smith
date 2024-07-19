from unittest.mock import Mock, call, patch

from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config
from githubapp.event_check_run import CheckRunConclusion, CheckRunStatus
from githubapp.events import CheckSuiteRequestedEvent, CheckSuiteRerequestedEvent

from tests.managers.pull_request_manager import ManagerCheckRunTestCase


class TestReleaseCheckRun(ManagerCheckRunTestCase):
    event_types = [CheckSuiteRequestedEvent, CheckSuiteRerequestedEvent]

    def setup_method(self, method):
        super().setup_method(method)

        # def repository_get_branch(self_, branch_name):
        #     return Mock(name=branch_name, protected=branch_name == self_.default_branch)

        self.pull_request = Mock(
            spec=PullRequest,
        )
        commit = Mock(commit=Mock(message="blank"))
        self.commits = [commit]

        self.pull_request.get_commits().reversed = self.commits
        # self.patch(patch.object(Repository, "get_branch", repository_get_branch))
        self.patch(
            patch.object(Repository, "get_pulls", return_value=[self.pull_request])
        )
        compare = Mock()
        compare.commits.reversed = self.commits
        self.patch(patch.object(Repository, "compare", return_value=compare))

    def add_commit_with_message(self, message):
        self.commits.append(Mock(commit=Mock(message=message)))

    @staticmethod
    def setup_config():
        Config.release_manager.set_values(enabled=True, update_in_file=False)
        Config.issue_manager.enabled = False
        Config.pull_request_manager.enabled = False

    def test_when_head_branch_is_not_default_branch(self, event_type, repository):
        self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

        repository.create_git_release.assert_not_called()

        self.assert_check_run_calls(
            "Release Manager",
            [
                call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
                call(title="Checking for release command..."),
                call(
                    title="No release command found",
                    conclusion=CheckRunConclusion.SUCCESS,
                ),
            ],
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_head_branch_is_not_default_branch_and_there_is_no_pull_request(
        self, event_type, repository
    ):
        with patch.object(Repository, "get_pulls", return_value=[]):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            repository.create_git_release.assert_not_called()

            self.assert_check_run_calls(
                "Release Manager",
                [
                    call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
                    call(
                        title="No Pull Request found",
                        conclusion=CheckRunConclusion.SUCCESS,
                    ),
                ],
            )

            self.assert_all_check_runs_calls_asserted()

    def test_when_is_the_first_commit(self, event_type, repository):
        self.deliver(
            event_type,
            check_suite={
                "head_branch": "feature_branch",
                "before": "0000000000000000000000000000000000000000",
            },
        )

        repository.create_git_release.assert_not_called()

        self.assert_check_run_calls(
            "Release Manager",
            [
                call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
                call(title="First commit", conclusion=CheckRunConclusion.SUCCESS),
            ],
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_head_branch_is_default_branch(self, event_type, repository):
        self.deliver(event_type, check_suite={"head_branch": "default_branch"})

        repository.create_git_release.assert_not_called()

        self.assert_check_run_calls(
            "Release Manager",
            [
                call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
                call(title="Checking for release command..."),
                call(
                    title="No release command found",
                    conclusion=CheckRunConclusion.SUCCESS,
                ),
            ],
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_has_invalid_release_command(self, event_type, repository):
        self.add_commit_with_message("[release:version]")
        self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

        repository.create_git_release.assert_not_called()

        self.assert_check_run_calls(
            "Release Manager",
            [
                call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
                call(title="Checking for release command..."),
                call(
                    title=f"Invalid release version",
                    summary="Invalid release ❌",
                    conclusion=CheckRunConclusion.FAILURE,
                ),
            ],
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_has_release_command_and_not_in_default_branch(
        self, event_type, repository
    ):
        self.add_commit_with_message("[release:1.2.3]")
        self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

        repository.create_git_release.assert_not_called()

        self.assert_check_run_calls(
            "Release Manager",
            [
                call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
                call(title="Checking for release command..."),
                call(
                    title="Ready to release 1.2.3",
                    summary="Release command found ✅",
                    conclusion=CheckRunConclusion.SUCCESS,
                ),
            ],
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_has_release_command_and_in_default_branch(
        self, event_type, repository
    ):
        self.add_commit_with_message("[release:1.2.3]")
        self.mock_request(
            "post",
            "/repos/heitorpolidoro/bartholomew-smith/releases",
            {
                "status": 200,
            },
        )
        self.deliver(event_type, check_suite={"head_branch": "default_branch"})

        repository.create_git_release.assert_not_called()

        self.assert_check_run_calls(
            "Release Manager",
            [
                call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
                call(title="Checking for release command..."),
                call(title="Releasing 1.2.3..."),
                call(title="1.2.3 released ✅", conclusion=CheckRunConclusion.SUCCESS),
            ],
        )

        self.assert_all_check_runs_calls_asserted()

    def test_when_has_relative_release_command(self, event_type, repository):
        self.add_commit_with_message("[release:major]")
        with patch.object(
            Repository, "get_latest_release", return_value=Mock(tag_name="1.2.3")
        ):
            self.deliver(event_type, check_suite={"head_branch": "feature_branch"})

            repository.create_git_release.assert_not_called()

            self.assert_check_run_calls(
                "Release Manager",
                [
                    call(title="Initializing...", status=CheckRunStatus.IN_PROGRESS),
                    call(title="Checking for release command..."),
                    call(
                        title="Ready to release 2.0.0",
                        summary="Release command found ✅",
                        conclusion=CheckRunConclusion.SUCCESS,
                    ),
                ],
            )

            self.assert_all_check_runs_calls_asserted()
