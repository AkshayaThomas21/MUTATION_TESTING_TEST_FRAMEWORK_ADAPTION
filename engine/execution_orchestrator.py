"""
Stage 3 — Parallel Execution Orchestrator.

Wraps the existing clone-based parallel runner with the missing abstractions:
an explicit resource manager, a scheduler, a job queue, and per-job timing /
retry / failure isolation.

Workspace isolation is done by directory cloning (Phase-1 design). A Docker
backend can be slotted in via the `runner` callable without touching callers,
so the architecture stays container-ready.

Components:
    ResourceManager  -> chooses worker count from CPU / config (NEW)
    TestScheduler    -> FIFO queue + ThreadPool dispatch with retry (NEW)
    Orchestrator     -> isolates each mutant, runs, collects timed results (NEW wrap)
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any


@dataclass
class ExecutionJob:
    job_id: str
    method: str
    mutant_id: Any
    payload: Dict[str, Any] = field(default_factory=dict)   # original/mutated code etc.
    attempts: int = 0


@dataclass
class JobResult:
    job_id: str
    method: str
    mutant_id: Any
    status: str                 # Killed | Survived | Equivalent | Build-error | Error
    duration_s: float = 0.0
    detail: str = ""
    isolated_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class ResourceManager:
    """Decides how many workers to use and provides a clean isolation root."""

    def __init__(self, max_workers: Optional[int] = None, isolation_root: str = "clones") -> None:
        cpu = os.cpu_count() or 4
        # Leave one core free; never exceed the configured cap.
        self.max_workers = max(1, min(max_workers or 4, cpu))
        self.isolation_root = isolation_root

    def workspace_for(self, job: ExecutionJob) -> str:
        return os.path.join(self.isolation_root, job.method, str(job.mutant_id))

    def summary(self) -> Dict[str, Any]:
        return {
            "max_workers": self.max_workers,
            "cpu_count": os.cpu_count(),
            "isolation_root": self.isolation_root,
        }


class TestScheduler:
    """FIFO queue dispatched across a ThreadPool, with single retry on failure."""

    def __init__(self, resources: ResourceManager, max_retries: int = 1) -> None:
        self.resources = resources
        self.max_retries = max_retries
        self._queue: "deque[ExecutionJob]" = deque()

    def submit(self, job: ExecutionJob) -> None:
        self._queue.append(job)

    def submit_all(self, jobs: List[ExecutionJob]) -> None:
        self._queue.extend(jobs)

    @property
    def pending(self) -> int:
        return len(self._queue)

    def run(self, runner: Callable[[ExecutionJob], JobResult]) -> List[JobResult]:
        """`runner(job) -> JobResult`. Failed jobs are retried up to max_retries."""
        results: List[JobResult] = []
        jobs = list(self._queue)
        self._queue.clear()

        def _wrapped(job: ExecutionJob) -> JobResult:
            start = time.perf_counter()
            try:
                res = runner(job)
            except Exception as e:  # isolate a crashing job from the rest
                res = JobResult(job.job_id, job.method, job.mutant_id, "Error", detail=str(e))
            if not res.duration_s:
                res.duration_s = round(time.perf_counter() - start, 4)
            return res

        with ThreadPoolExecutor(max_workers=self.resources.max_workers) as pool:
            futures = {pool.submit(_wrapped, j): j for j in jobs}
            for fut in as_completed(futures):
                job = futures[fut]
                res = fut.result()
                if res.status == "Error" and job.attempts < self.max_retries:
                    job.attempts += 1
                    self._queue.append(job)   # requeue for a retry pass
                else:
                    results.append(res)

        # Drain retries (sequentially — they are the exception, not the rule).
        while self._queue:
            job = self._queue.popleft()
            results.append(_wrapped(job))
        return results


class ParallelExecutionOrchestrator:
    """Stage 3 façade."""

    def __init__(self, max_workers: Optional[int] = None, isolation_root: str = "clones") -> None:
        self.resources = ResourceManager(max_workers, isolation_root)
        self.scheduler = TestScheduler(self.resources)

    def build_jobs(self, mutants: List[Any]) -> List[ExecutionJob]:
        """Accepts ScoredMutant objects or plain dicts."""
        jobs: List[ExecutionJob] = []
        for i, m in enumerate(mutants, start=1):
            if hasattr(m, "to_dict"):
                method, mid = m.method, m.mutant_id
                payload = m.to_dict()
            else:
                method = (m.get("method") or m.get("function_name") or "c1").split("(")[0].strip()
                mid = m.get("mutant_id", m.get("id", i))
                payload = dict(m)
            jobs.append(ExecutionJob(f"job-{i}", method, mid, payload))
        return jobs

    def run(
        self, mutants: List[Any], runner: Callable[[ExecutionJob], JobResult]
    ) -> List[JobResult]:
        self.scheduler.submit_all(self.build_jobs(mutants))
        return self.scheduler.run(runner)

    # -- offline demo runner: derive status from the mutant payload ------ #
    @staticmethod
    def simulated_runner(job: ExecutionJob) -> JobResult:
        """No build needed — uses a provided status, else infers from confidence."""
        payload = job.payload
        status = payload.get("status")
        if not status:
            conf = payload.get("confidence", 70)
            if conf < 30:
                status = "Equivalent"       # very low confidence ~ likely equivalent
            elif conf >= 80:
                status = "Killed"
            else:
                status = "Survived"
        # A touch of simulated work so timing is non-zero and varied.
        time.sleep(0.005)
        return JobResult(
            job.job_id, job.method, job.mutant_id, status,
            detail="simulated", isolated_path=f"clones/{job.method}/{job.mutant_id}",
        )
