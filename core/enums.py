from enum import Enum

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"
    CANCELLED = "cancelled"


class RetryStrategy(Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
