from threading import RLock
from typing import Protocol
from copy import deepcopy


class JobRepository(Protocol):
    lock: RLock
    def all(self) -> list[dict]: ...
    def get(self, job_id: str) -> dict: ...
    def put(self, job: dict) -> None: ...
    def update(self, job_id: str, **changes) -> None: ...


class MemoryRepository:
    """Snapshots isolate SSE readers from worker mutations; lock covers transactions."""
    def __init__(self):
        self.lock = RLock()
        self._jobs = {}

    def all(self):
        with self.lock:
            return deepcopy(list(self._jobs.values()))

    def get(self, job_id):
        with self.lock:
            return deepcopy(self._jobs[job_id])

    def put(self, job):
        with self.lock:
            self._jobs[job['id']] = deepcopy(job)

    def update(self, job_id, **changes):
        with self.lock:
            self._jobs[job_id].update(changes)
