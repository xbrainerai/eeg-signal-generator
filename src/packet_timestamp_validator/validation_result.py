from enum import Enum
from dataclasses import dataclass

class ValidationStatus(Enum):
    VALID = "VALID"
    WARN = "WARN"
    ERROR = "ERROR"

@dataclass
class ValidationResult:
    status: ValidationStatus
    reason: str = ""
    delta_ms: float = 0.0
