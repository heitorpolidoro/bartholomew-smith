from src.helpers.db_helper import BaseModelService
from src.models import Job, JobStatus


class JobService(BaseModelService[Job]):
    @classmethod
    def update_status(cls, job, new_status: JobStatus):
        job.job_status = new_status
        JobService.update(job)

    @classmethod
    def to_done(cls, job):
        cls.update_status(job, JobStatus.DONE)
