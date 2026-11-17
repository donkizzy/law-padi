from datetime import UTC, datetime

RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH = 2048


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)
