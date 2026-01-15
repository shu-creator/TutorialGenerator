"""Tests for utility functions."""

from app.utils.timecode import mmss_to_seconds, seconds_to_mmss


class TestTimecode:
    """Tests for timecode utilities."""

    def test_seconds_to_mmss_zero(self):
        assert seconds_to_mmss(0) == "00:00"

    def test_seconds_to_mmss_simple(self):
        assert seconds_to_mmss(65) == "01:05"

    def test_seconds_to_mmss_large(self):
        assert seconds_to_mmss(3661) == "61:01"

    def test_mmss_to_seconds_zero(self):
        assert mmss_to_seconds("00:00") == 0

    def test_mmss_to_seconds_simple(self):
        assert mmss_to_seconds("01:30") == 90

    def test_mmss_to_seconds_hhmmss(self):
        assert mmss_to_seconds("01:01:30") == 3690
