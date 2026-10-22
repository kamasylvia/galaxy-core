"""Tests for scheduler configuration loading."""

from galaxy_core.shared_kernel.utils.config_loader import get_section


class TestSchedulerConfig:
    """Tests for scheduler config section."""

    def test_get_section_returns_dict(self):
        """get_section('scheduler') should return a dict."""
        config = get_section("scheduler")
        assert isinstance(config, dict)

    def test_default_enabled_intervals(self):
        """Default enabled_intervals should include day/week/month/season/year."""
        config = get_section("scheduler")
        enabled = config.get("enabled_intervals", [])
        for interval in ["day", "week", "month", "season", "year"]:
            assert interval in enabled, f"'{interval}' missing from enabled_intervals"

    def test_default_security_type(self):
        """Default security_type should be SH_A or EXTRA_ETF."""
        config = get_section("scheduler")
        security_type = config.get("security_type", "")
        assert security_type in ("SH_A", "EXTRA_ETF"), (
            f"Unexpected security_type: {security_type}"
        )

    def test_config_has_trigger_hours(self):
        """Config should contain kline_trigger_hour and check_trigger_hour."""
        config = get_section("scheduler")
        assert "kline_trigger_hour" in config, "Missing kline_trigger_hour"
        assert "check_trigger_hour" in config, "Missing check_trigger_hour"
        assert isinstance(config["kline_trigger_hour"], int)
        assert isinstance(config["check_trigger_hour"], int)

    def test_config_has_retry_settings(self):
        """Config should contain max_retries and retry_delay_minutes."""
        config = get_section("scheduler")
        assert "max_retries" in config, "Missing max_retries"
        assert "retry_delay_minutes" in config, "Missing retry_delay_minutes"
        assert isinstance(config["max_retries"], int)
        assert isinstance(config["retry_delay_minutes"], int)

    def test_config_has_check_ranges(self):
        """Config should contain check_ranges with security type entries."""
        config = get_section("scheduler")
        check_ranges = config.get("check_ranges", {})
        assert isinstance(check_ranges, dict)
        assert len(check_ranges) > 0, "check_ranges should not be empty"

    def test_config_has_routine_lookback(self):
        """Config should contain routine_lookback_periods."""
        config = get_section("scheduler")
        lookback = config.get("routine_lookback_periods", 0)
        assert isinstance(lookback, int)
        assert lookback > 0, "routine_lookback_periods should be positive"
