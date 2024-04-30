"""IssueJob model"""

from enum import Enum

from src.helpers.db_helper import BaseModel


class IssueJobStatus(Enum):
    """IssueJobStatus enum"""

    PENDING = "pending"
    RUNNING = "running"
    ERROR = "error"
    DONE = "done"


class IssueJob(BaseModel):
    """IssueJob model"""

    key_schema = ["issue_url"]
    issue_url: str
    repository_url: str
    title: str
    issue_job_status: IssueJobStatus = IssueJobStatus.PENDING
    issue_comment_id: int
    hook_installation_target_id: int
    installation_id: int
