"""Resume Matcher boundary; no HTTP API details or credentials are configured yet."""
from __future__ import annotations

from typing import Protocol


class IntegrationUnavailable(RuntimeError):
    """Raised when an operation is requested without a configured remote adapter."""


class ResumeMatcherAdapter(Protocol):
    def availability(self) -> dict: ...

    def submit(self, payload: dict, idempotency_key: str) -> dict: ...

    def get_operation(self, operation_id: str) -> dict: ...


class NotConfiguredAdapter:
    """Honest unavailable state used until an authenticated API contract is supplied."""

    def availability(self) -> dict:
        return {
            "name": "Resume Matcher",
            "status": "not_configured",
            "available": False,
            "message": "No API endpoint or server credential is configured. Prepare a local packet and use the documented manual handoff.",
        }

    def submit(self, payload: dict, idempotency_key: str) -> dict:
        raise IntegrationUnavailable("Resume Matcher API is not configured; no request was sent")

    def get_operation(self, operation_id: str) -> dict:
        raise IntegrationUnavailable("Resume Matcher API is not configured; no operation can be queried")


def get_adapter() -> ResumeMatcherAdapter:
    """Return the explicitly unavailable adapter until a real API contract is implemented."""
    return NotConfiguredAdapter()
