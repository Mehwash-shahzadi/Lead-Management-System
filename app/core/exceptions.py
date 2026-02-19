class ThinkRealtyError(Exception):
    """Base class for all ThinkRealty domain exceptions.

    Every custom exception in this module inherits from here so that a
    single ``except ThinkRealtyError`` clause can catch any domain
    error.
    """

    def __init__(self, detail: str = "An error occurred"):
        self.detail = detail
        super().__init__(detail)


class LeadNotFoundError(ThinkRealtyError):
    """Raised when a requested lead does not exist."""

    def __init__(self, detail: str = "Lead not found"):
        super().__init__(detail)


class AgentNotFoundError(ThinkRealtyError):
    """Raised when a requested agent does not exist."""

    def __init__(self, detail: str = "Agent not found"):
        super().__init__(detail)


class AssignmentNotFoundError(ThinkRealtyError):
    """Raised when a lead assignment does not exist."""

    def __init__(self, detail: str = "Assignment not found"):
        super().__init__(detail)


class NoAgentAssignedError(ThinkRealtyError):
    """Raised when an operation requires an assigned agent but none exists."""

    def __init__(self, detail: str = "No agent assigned to lead"):
        super().__init__(detail)


class DuplicateLeadError(ThinkRealtyError):
    """Raised when a duplicate lead is detected."""

    def __init__(self, detail: str = "Duplicate lead detected"):
        super().__init__(detail)


class FollowUpConflictError(ThinkRealtyError):
    """Raised when there are conflicting follow-up schedules."""

    def __init__(self, detail: str = "Conflicting follow-up schedule"):
        super().__init__(detail)


class InvalidLeadDataError(ThinkRealtyError):
    """Raised when lead data is invalid."""

    def __init__(self, detail: str = "Invalid lead data"):
        super().__init__(detail)


class InvalidStatusTransitionError(ThinkRealtyError):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, detail: str = "Invalid status transition"):
        super().__init__(detail)


class AgentOverloadError(ThinkRealtyError):
    """Raised when an agent has reached maximum capacity.

    The default message mirrors the PostgreSQL trigger
    ``trg_enforce_agent_max_workload`` for consistency across all
    enforcement layers (CHECK constraint, trigger, application).
    """

    def __init__(
        self, detail: str = "Agent has reached maximum capacity of 50 active leads"
    ):
        super().__init__(detail)


class PropertyServiceUnavailableError(ThinkRealtyError):
    """Raised when property suggestion service is unavailable."""

    def __init__(self, detail: str = "Property service unavailable"):
        super().__init__(detail)


class OverdueTaskError(ThinkRealtyError):
    """Raised when a follow-up task is overdue beyond the allowed limit.

    In production the PostgreSQL trigger ``trg_block_overdue_follow_up``
    raises before this fires.  Kept for application-level enforcement
    and non-PostgreSQL backends (e.g. test suites using SQLite).
    """

    def __init__(self, detail: str = "Follow-up task is overdue beyond allowed limit"):
        super().__init__(detail)
