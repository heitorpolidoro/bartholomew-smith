from enum import Enum
from typing import Optional

from src.helpers.db_helper import BaseModel


class JobStatus(Enum):
    PENDING = "pending"
    UPDATE_ISSUE_BODY = "update_issue_body"
    ERROR = "error"
    DONE = "done"


class Job(BaseModel):
    class Config:
        key_schema = ["task", "original_issue_ref"]
    task: str
    original_issue_ref: str
    checked: bool
    issue_comment_id: int
    job_status: JobStatus = JobStatus.PENDING
    hook_installation_target_id: int
    installation_id: int
    issue_ref: Optional[str] = None
