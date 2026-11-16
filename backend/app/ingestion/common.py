from datetime import UTC, datetime


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


def enum_value(value: object) -> str:
    return str(getattr(value, "value", value))
