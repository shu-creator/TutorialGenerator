"""Timecode utilities."""


def seconds_to_mmss(seconds: float) -> str:
    """
    Convert seconds to MM:SS format.

    Args:
        seconds: Time in seconds

    Returns:
        Time in MM:SS format
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def mmss_to_seconds(mmss: str) -> float:
    """
    Convert MM:SS format to seconds.

    Args:
        mmss: Time in MM:SS format

    Returns:
        Time in seconds
    """
    parts = mmss.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        # HH:MM:SS format
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0.0
