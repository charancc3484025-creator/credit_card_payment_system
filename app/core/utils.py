import uuid
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_reference(prefix: str = "PAY") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16].upper()}"
