from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Select

from app.core.exceptions import BusinessError
from app.models import Transaction

LOCAL_TZ = ZoneInfo("Asia/Kolkata")


def _local_day_start_utc(day: date) -> datetime:
    local_start = datetime.combine(day, time.min, tzinfo=LOCAL_TZ)
    return local_start.astimezone(timezone.utc).replace(tzinfo=None)


def apply_transaction_filters(
    query: Select,
    txn_type: str | None = None,
    status: str | None = None,
    card_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    search: str | None = None,
) -> Select:
    if from_date and to_date and from_date > to_date:
        raise BusinessError("from_date cannot be after to_date.")
    if txn_type:
        query = query.where(Transaction.transaction_type == txn_type.upper())
    if status:
        query = query.where(Transaction.status == status.upper())
    if card_id:
        query = query.where(Transaction.card_id == card_id)
    if from_date:
        query = query.where(Transaction.created_at >= _local_day_start_utc(from_date))
    if to_date:
        query = query.where(Transaction.created_at < _local_day_start_utc(to_date + timedelta(days=1)))
    if min_amount is not None:
        query = query.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.where(Transaction.amount <= max_amount)
    if search:
        query = query.where(Transaction.reference_id.ilike(f"%{search.strip()}%"))
    return query
