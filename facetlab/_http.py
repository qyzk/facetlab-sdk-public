"""Shared response handling: every FacetLab error becomes a FacetLabError subclass with the server's code."""

from typing import Any, Dict

from .exceptions import AuthenticationError, FacetLabError, InsufficientFundsError, LimitError

LIMIT_CODES = {"free_tier_limit", "plan_limit", "quota_exceeded", "tier_limit"}


def check(response) -> Dict[str, Any]:
    """The JSON body of a successful response; raises a FacetLabError for anything else."""
    status = getattr(response, "status_code", None)
    try:
        body = response.json()
    except ValueError:
        body = None
    if response.ok:
        if body is None:
            raise FacetLabError(f"HTTP {status}: response was not valid JSON", code=f"http_{status}", details={"status": status})
        return body
    err = body.get("error") if isinstance(body, dict) else None
    # Two error shapes: {"error": {"code", "message", "details"}} and {"error": "message", "code": "..."}.
    if isinstance(err, dict):
        code, message, details = err.get("code"), err.get("message"), err.get("details") or {}
    else:
        code = body.get("code") if isinstance(body, dict) else None
        message, details = (err if isinstance(err, str) else None), (body.get("details") if isinstance(body, dict) else None) or {}
    if status == 413:
        raise FacetLabError("The request is too large (the server accepts about 4.5 MB). Compress or resize the images: "
                            "for UI A/B tests both screenshots together must stay under about 3 MB.", code="payload_too_large")
    code = code or f"http_{status}"
    message = message or f"HTTP {status}"
    if status == 401 or code == "unauthorized":
        raise AuthenticationError(message)
    if status == 402 and code == "insufficient_funds":
        raise InsufficientFundsError(message, required=details.get("required"), balance=details.get("balance"), details=details)
    if code in LIMIT_CODES:
        raise LimitError(message, code=code, details=details)
    raise FacetLabError(message, code=code, details=details)
