"""
Maps AlsoEnergy displayName strings (and Windows timezone IDs) to IANA names.
AlsoEnergy only returns displayName in the timeZone object — there is no .name field.
"""

_TZ_MAP: dict[str, str] = {
    # AlsoEnergy displayName strings seen in production data
    "(UTC-05:00) Eastern Time (US & Canada)": "America/New_York",
    "(UTC-04:00) Eastern Time (US & Canada)": "America/New_York",
    "(UTC-06:00) Central Time (US & Canada)": "America/Chicago",
    "(UTC-05:00) Central Time (US & Canada)": "America/Chicago",
    "(UTC-07:00) Mountain Time (US & Canada)": "America/Denver",
    "(UTC-06:00) Mountain Time (US & Canada)": "America/Denver",
    "(UTC-07:00) Arizona": "America/Phoenix",
    "(UTC-08:00) Pacific Time (US & Canada)": "America/Los_Angeles",
    "(UTC-07:00) Pacific Time (US & Canada)": "America/Los_Angeles",
    "(UTC-09:00) Alaska": "America/Anchorage",
    "(UTC-10:00) Hawaii": "Pacific/Honolulu",
    "(UTC-04:00) Atlantic Time (Canada)": "America/Halifax",
    "(UTC-03:30) Newfoundland": "America/St_Johns",
    "(UTC) Greenwich Mean Time : Dublin, Edinburgh, Lisbon, London": "Europe/London",
    "(UTC) UTC": "UTC",
    "(UTC+00:00) UTC": "UTC",
    # Windows timezone IDs (returned by some AlsoEnergy environments)
    "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago",
    "Mountain Standard Time": "America/Denver",
    "US Mountain Standard Time": "America/Phoenix",
    "Pacific Standard Time": "America/Los_Angeles",
    "Alaskan Standard Time": "America/Anchorage",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "Atlantic Standard Time": "America/Halifax",
    "Newfoundland Standard Time": "America/St_Johns",
    "GMT Standard Time": "Europe/London",
    "UTC": "UTC",
}


def resolve_iana(display_name: str | None) -> str:
    """
    Convert an AlsoEnergy timezone displayName to an IANA name.
    Returns the original prefixed with 'LEGACY:' if no mapping exists,
    so unmapped zones are visible in the CSV for future dict expansion.
    """
    if not display_name:
        return ""
    s = display_name.strip()
    # Already looks like IANA (contains '/' and no spaces)
    if "/" in s and " " not in s:
        return s
    # Direct lookup
    if s in _TZ_MAP:
        return _TZ_MAP[s]
    # Strip existing LEGACY: prefix and retry
    if s.startswith("LEGACY:"):
        inner = s[7:].strip()
        if inner in _TZ_MAP:
            return _TZ_MAP[inner]
        return s  # already prefixed, leave as-is
    import logging
    logging.getLogger(__name__).warning("unmapped timezone displayName: %r", s)
    return f"LEGACY:{s}"
