from enum import Enum
from typing import Optional

from src.helpers.db_helper import BaseModel


class JobStatus(Enum):
    PENDING = "pending"
    UPDATE_ISSUE_STATUS = "update_issue_status"
    CREATE_ISSUE = "create_issue"
    UPDATE_ISSUE_BODY = "update_issue_body"
    ERROR = "error"
    DONE = "done"


class Job(BaseModel):
    key_schema = ["task", "original_issue_url"]
    task: str
    original_issue_url: str
    checked: bool
    job_status: JobStatus = JobStatus.PENDING
    repository_url: Optional[str] = None
    title: Optional[str] = None
    milestone: Optional[str] = None
    issue_ref: Optional[str] = None
    issue_url: Optional[str] = None
