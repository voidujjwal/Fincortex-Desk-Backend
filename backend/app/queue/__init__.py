import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Dict

logger = logging.getLogger("tradingagents.queue")


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    job_id: str
    task: Callable[..., Any]
    status: JobStatus = JobStatus.QUEUED
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AsyncioJobQueue:
    """In-memory async job queue using asyncio.

    Designed to be swappable with Redis + Celery/Dramatiq later
    without changing the interface.
    """

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._tasks: Dict[str, asyncio.Task] = {}

    async def enqueue(self, job: Job) -> Job:
        """Enqueue a job and start it as a background asyncio task."""
        self._jobs[job.job_id] = job
        task = asyncio.create_task(self._run_job(job))
        self._tasks[job.job_id] = task
        return job

    async def _run_job(self, job: Job) -> None:
        """Execute a job and update its status."""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        try:
            result = await job.task()
            job.result = result
            job.status = JobStatus.COMPLETED
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            raise
        except Exception as exc:
            job.error = str(exc)
            job.status = JobStatus.FAILED
            logger.error("Job %s failed: %s", job.job_id, exc)
        finally:
            job.completed_at = datetime.utcnow()

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        return self._jobs.get(job_id)

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running job."""
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def list_jobs(self, status: Optional[JobStatus] = None) -> list:
        """List all jobs, optionally filtered by status."""
        if status:
            return [j for j in self._jobs.values() if j.status == status]
        return list(self._jobs.values())