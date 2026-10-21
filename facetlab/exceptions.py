"""
FacetLab SDK Exceptions
"""


class FacetLabError(Exception):
    """Base exception for all FacetLab SDK errors."""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(FacetLabError):
    """Raised when API key is invalid or missing."""
    
    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(message, code="AUTH_ERROR")


class RateLimitError(FacetLabError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(message, code="RATE_LIMIT")
        self.retry_after = retry_after


class TierLimitError(FacetLabError):
    """Raised when user's tier doesn't support the requested feature."""
    
    def __init__(self, message: str, required_tier: str = None):
        super().__init__(message, code="TIER_LIMIT")
        self.required_tier = required_tier


class ValidationError(FacetLabError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(message, code="VALIDATION_ERROR")
        self.field = field


class ExperimentError(FacetLabError):
    """Raised when experiment processing fails."""
    
    def __init__(self, message: str, job_id: str = None):
        super().__init__(message, code="EXPERIMENT_ERROR")
        self.job_id = job_id


class MockupGenerationError(FacetLabError):
    """Raised when mockup generation fails."""
    
    def __init__(self, message: str, recommendation: str = None):
        super().__init__(message, code="MOCKUP_ERROR")
        self.recommendation = recommendation


class InsufficientFundsError(FacetLabError):
    """Raised when the prepaid balance does not cover a test (HTTP 402 insufficient_funds).

    `required` and `balance` are in US dollars. Top up on the Billing page:
    https://qyzkdesign.com/dashboard/billing
    """

    def __init__(self, message: str, required: float = None, balance: float = None, details: dict = None):
        super().__init__(message, code="insufficient_funds", details=details)
        self.required = required
        self.balance = balance


class LimitError(FacetLabError):
    """Raised when a free-test, plan or quota limit is reached (free_tier_limit, plan_limit, quota_exceeded)."""
