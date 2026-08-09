"""Supported case-display timezone policy and formatting helpers."""

from datetime import UTC, datetime

from ioc_evidence_packager.domain.errors import ValidationError

UTC_DISPLAY = "UTC"
LOCAL_DISPLAY = "Local system time"
SUPPORTED_DISPLAY_TIMEZONES = (UTC_DISPLAY, LOCAL_DISPLAY)


def normalize_display_timezone(value: str) -> str:
    """Validate and normalize the portable timezone choices supported by the app."""

    normalized = " ".join(value.split())
    match = next(
        (
            candidate
            for candidate in SUPPORTED_DISPLAY_TIMEZONES
            if candidate.casefold() == normalized.casefold()
        ),
        None,
    )
    if match is None:
        raise ValidationError("Display timezone must be UTC or Local system time.")
    return match


def format_case_datetime(
    value: datetime,
    display_timezone: str,
    pattern: str = "%Y-%m-%d %H:%M:%S %Z",
) -> str:
    """Format an aware timestamp using the case display policy."""

    converted = value.astimezone() if display_timezone == LOCAL_DISPLAY else value.astimezone(UTC)
    return converted.strftime(pattern)
