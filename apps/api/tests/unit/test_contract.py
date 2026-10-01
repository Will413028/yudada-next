from uuid import UUID

import pytest
from pydantic import ValidationError

from app.main import AppSummary, app


def test_app_summary_rejects_invalid_identity() -> None:
    with pytest.raises(ValidationError):
        AppSummary(id="not-a-uuid", name="Example")  # type: ignore[arg-type]
    assert AppSummary(id=UUID(int=1), name="Example").model_dump(mode="json")["name"] == "Example"


def test_openapi_never_exposes_transport_probes() -> None:
    paths = set(app.openapi()["paths"])
    assert {"/api/v1/health", "/api/v1/apps", "/api/v1/auth/login"} <= paths
    assert all(path.startswith("/api/v1/") for path in paths)
    assert not any("probe" in path for path in paths)
