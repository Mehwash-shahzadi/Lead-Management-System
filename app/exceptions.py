"""Custom exceptions for ThinkRealty application."""

from fastapi import HTTPException


class DuplicateLeadError(HTTPException):
    """Raised when a duplicate lead is detected."""

    def __init__(self, detail: str = "Duplicate lead detected"):
        super().__init__(status_code=400, detail=detail)


class AgentOverloadError(HTTPException):
    """Raised when an agent has reached maximum capacity."""

    def __init__(self, detail: str = "Agent overload - no capacity"):
        super().__init__(status_code=503, detail=detail)


class InvalidLeadDataError(HTTPException):
    """Raised when lead data is invalid."""

    def __init__(self, detail: str = "Invalid lead data"):
        super().__init__(status_code=422, detail=detail)


class FollowUpConflictError(HTTPException):
    """Raised when there are conflicting follow-up schedules."""

    def __init__(self, detail: str = "Conflicting follow-up schedule"):
        super().__init__(status_code=409, detail=detail)


class InvalidStatusTransitionError(HTTPException):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, detail: str = "Invalid status transition"):
        super().__init__(status_code=400, detail=detail)


class PropertyServiceUnavailableError(HTTPException):
    """Raised when property suggestion service is unavailable."""

    def __init__(self, detail: str = "Property service unavailable"):
        super().__init__(status_code=503, detail=detail)