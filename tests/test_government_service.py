from __future__ import annotations

import pytest

from citadel_toolbox_mcp.services import GovernmentService


def test_known_application_status_is_returned() -> None:
    result = GovernmentService().get_application_status("app-1001")

    assert result["status"] == "under_review"
    assert result["application_id"] == "APP-1001"


def test_unknown_application_does_not_leak_other_records() -> None:
    result = GovernmentService().get_application_status("APP-9999")

    assert result == {
        "application_id": "APP-9999",
        "status": "not_found",
        "updated_at": "",
        "next_step": "Verify the application identifier with the user.",
    }


def test_service_request_requires_complete_input() -> None:
    with pytest.raises(ValueError, match="required"):
        GovernmentService().create_service_request("", "Need assistance")


def test_service_request_is_created() -> None:
    result = GovernmentService().create_service_request("licensing", "Renew trade license")

    assert result["request_id"].startswith("REQ-")
    assert result["status"] == "submitted"