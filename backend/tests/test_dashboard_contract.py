"""Dashboard contract regression tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.adapters.persistence.repositories import (
    InMemoryAccountRepository,
    InMemoryClientRepository,
    InMemoryJobRepository,
    InMemoryStatusRepository,
)
from app.application.use_cases.logs import LogsUseCases


def test_get_dashboard_data_returns_canonical_snake_case_contract():
    account_repo = InMemoryAccountRepository()
    client_repo = InMemoryClientRepository()
    status_repo = InMemoryStatusRepository()
    job_repo = InMemoryJobRepository()
    usecases = LogsUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        job_repo=job_repo,
    )

    account_repo.set("acct-active", {"username": "alpha", "followers": 900, "proxy": None})
    account_repo.set("acct-error", {"username": "beta", "followers": 300, "proxy": "http://proxy:8080"})
    client_repo.set("acct-active", object())
    status_repo.set("acct-error", "error")

    today_prefix = datetime.now(UTC).date().isoformat()
    yesterday_prefix = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()

    job_repo.set(
        "job-1",
        {
            "id": "job-1",
            "caption": "Today completed",
            "status": "completed",
            "targets": [{"accountId": "acct-active"}],
            "results": [],
            "createdAt": f"{today_prefix}T01:00:00Z",
            "mediaUrls": [],
            "mediaType": "photo",
        },
    )
    job_repo.set(
        "job-2",
        {
            "id": "job-2",
            "caption": "Today failed",
            "status": "failed",
            "targets": [{"accountId": "acct-error"}],
            "results": [],
            "createdAt": f"{today_prefix}T02:00:00Z",
            "mediaUrls": [],
            "mediaType": "photo",
        },
    )
    job_repo.set(
        "job-3",
        {
            "id": "job-3",
            "caption": "Yesterday completed",
            "status": "completed",
            "targets": [{"accountId": "acct-active"}],
            "results": [],
            "createdAt": f"{yesterday_prefix}T01:00:00Z",
            "mediaUrls": [],
            "mediaType": "photo",
        },
    )

    payload = usecases.get_dashboard_data()

    assert payload["contract_version"] == 1
    assert set(payload) == {
        "contract_version",
        "accounts",
        "error_accounts",
        "jobs_today",
        "recent_jobs",
        "top_accounts",
    }
    assert payload["accounts"] == {
        "total": 2,
        "active": 1,
        "idle": 0,
        "error": 1,
    }
    assert "errorAccounts" not in payload["accounts"]
    assert "jobsToday" not in payload
    assert "recentJobs" not in payload
    assert "topAccounts" not in payload

    assert payload["error_accounts"] == [
        {
            "id": "acct-error",
            "username": "beta",
            "error": "",
            "proxy": "http://proxy:8080",
            "status": "error",
        }
    ]
    assert payload["jobs_today"] == {
        "total": 2,
        "completed": 1,
        "partial": 0,
        "failed": 1,
    }
    assert [job["id"] for job in payload["recent_jobs"]] == ["job-1", "job-2", "job-3"]
    assert payload["top_accounts"][0]["id"] == "acct-active"
