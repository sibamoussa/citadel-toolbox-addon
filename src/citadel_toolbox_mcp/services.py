from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True)
class ApplicationStatus:
    application_id: str
    status: str
    updated_at: str
    next_step: str


@dataclass(frozen=True)
class ServiceRequest:
    request_id: str
    service: str
    summary: str
    status: str
    created_at: str


class GovernmentService:
    """In-memory demonstration adapter; replace it before any production deployment."""

    def __init__(self) -> None:
        self._applications = {
            "APP-1001": ApplicationStatus(
                application_id="APP-1001",
                status="under_review",
                updated_at="2026-10-10T09:30:00Z",
                next_step="No action required. The entity is reviewing the application.",
            ),
            "APP-1002": ApplicationStatus(
                application_id="APP-1002",
                status="information_required",
                updated_at="2026-10-12T14:00:00Z",
                next_step="Submit the requested identity document through the approved portal.",
            ),
        }
        self._requests: dict[str, ServiceRequest] = {}

    def get_application_status(self, application_id: str) -> dict[str, str]:
        normalized = application_id.strip().upper()
        application = self._applications.get(normalized)
        if application is None:
            return {
                "application_id": normalized,
                "status": "not_found",
                "updated_at": "",
                "next_step": "Verify the application identifier with the user.",
            }
        return asdict(application)

    def create_service_request(self, service: str, summary: str) -> dict[str, str]:
        if not service.strip() or not summary.strip():
            raise ValueError("service and summary are required")
        request = ServiceRequest(
            request_id=f"REQ-{uuid4().hex[:8].upper()}",
            service=service.strip(),
            summary=summary.strip(),
            status="submitted",
            created_at=datetime.now(UTC).isoformat(),
        )
        self._requests[request.request_id] = request
        return asdict(request)