"""DB services for the models"""

from src.helpers.db_helper import BaseModelService
from src.models import IssueJob, Job


class IssueJobService(BaseModelService[IssueJob]):
    """DB Service for IssueJob model"""


class JobService(BaseModelService[Job]):
    """DB Service for Job model"""
