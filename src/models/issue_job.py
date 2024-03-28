from enum import Enum
from typing import Optional

from pydantic import ConfigDict

from src.helpers.db_helper import BaseModel


class IssueJobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    ERROR = "error"
    DONE = "done"


class IssueJob(BaseModel):
    key_schema = ["issue_url"]
    issue_url: str
    repository_url: str
    title: str
    issue_job_status: IssueJobStatus = IssueJobStatus.PENDING
    issue_comment_id: int
    hook_installation_target_id: int
    installation_id: int
