from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.memory.manual_dreaming import ManualDreamingNoEvidence
from tests.api.auth_helpers import build_auth_service, issue_session


class FakeDreamingService:
    def __init__(self) -> None:
        self.owner = None

    def start(self, owner_id: str, local_date: date):
        self.owner = owner_id
        return SimpleNamespace(id="job-1", status="queued", local_date=local_date.isoformat())

    async def run(self, owner_id: str, job_id: str) -> None:
        self.owner = owner_id

    def status(self, owner_id: str, job_id: str):
        if owner_id != self.owner:
            return None
        return {"job_id": job_id, "status": "completed", "result": {"id": "result-1"}}

    def today(self, owner_id: str, local_date: date):
        if owner_id != self.owner:
            return None
        return {"id": "result-1", "local_date": local_date.isoformat(), "version": 1}

    def confirm_hypothesis(self, owner_id: str, result_id: str, index: int):
        if owner_id != self.owner:
            raise ValueError("not found")
        return "hypothesis-1"


def test_manual_dreaming_api_starts_reads_and_confirms_for_current_owner(tmp_path) -> None:
    auth = build_auth_service(tmp_path / "auth.db")
    service = FakeDreamingService()
    client = TestClient(create_app(auth_service=auth, manual_dreaming_service=service))
    cookies = issue_session(auth, owner_id="owner-1")

    started = client.post("/v1/me/dreaming", cookies=cookies)
    assert started.status_code == 202
    assert started.json()["job_id"] == "job-1"
    assert client.get("/v1/me/dreaming/jobs/job-1", cookies=cookies).json()["status"] == "completed"
    assert client.get("/v1/me/dreaming/today", cookies=cookies).json()["id"] == "result-1"
    confirmed = client.post(
        "/v1/me/dreaming/results/result-1/hypotheses/0/confirm", cookies=cookies
    )
    assert confirmed.json() == {"memory_id": "hypothesis-1", "status": "confirmed"}


def test_manual_dreaming_api_handles_empty_evidence_and_owner_isolation(tmp_path) -> None:
    class EmptyService(FakeDreamingService):
        def start(self, owner_id: str, local_date: date):
            raise ManualDreamingNoEvidence("最近 7 天还没有足够内容")

    auth = build_auth_service(tmp_path / "auth.db")
    empty_client = TestClient(create_app(auth_service=auth, manual_dreaming_service=EmptyService()))
    cookies = issue_session(auth, owner_id="owner-1")
    assert empty_client.post("/v1/me/dreaming", cookies=cookies).status_code == 409

    service = FakeDreamingService()
    service.owner = "owner-1"
    client = TestClient(create_app(auth_service=auth, manual_dreaming_service=service))
    other = issue_session(auth, owner_id="owner-2")
    assert client.get("/v1/me/dreaming/jobs/job-1", cookies=other).status_code == 404
    assert client.get("/v1/me/dreaming/today", cookies=other).status_code == 404
