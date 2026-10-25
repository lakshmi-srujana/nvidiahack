from enum import StrEnum


class ErrorCode(StrEnum):
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    MISSION_BUSY = "MISSION_BUSY"
    STATE_STALE = "STATE_STALE"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    AI_TIMEOUT = "AI_TIMEOUT"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    MODEL_BAD_OUTPUT = "MODEL_BAD_OUTPUT"
    VERIFIER_UNAVAILABLE = "VERIFIER_UNAVAILABLE"
    VERIFIER_FAILED = "VERIFIER_FAILED"
    REPAIR_EXHAUSTED = "REPAIR_EXHAUSTED"
    EVENT_DUPLICATE = "EVENT_DUPLICATE"
    EVENT_OUT_OF_ORDER = "EVENT_OUT_OF_ORDER"
    BENCHMARK_NOT_FOUND = "BENCHMARK_NOT_FOUND"


class ServiceError(Exception):
    def __init__(self, code: ErrorCode, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable
