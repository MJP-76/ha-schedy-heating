"""Tests for Schedy Heating climate entity."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.schedy_heating.climate import SchedyClimate
from custom_components.schedy_heating.const import (
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_DAY_TEMP,
    CONF_DEFAULT_TEMP,
    CONF_NIGHT_TEMP,
    CONF_USE_WEEKEND_SCHEDULE,
    CONF_WEEKEND_DAY_END,
    CONF_WEEKEND_DAY_START,
    CONF_WEEKEND_DAY_TEMP,
    CONF_WEEKEND_NIGHT_TEMP,
    DEFAULT_TARGET_TEMP,
)


@pytest.fixture
def mock_climate_entity(mock_hass):
    """Create a mock SchedyClimate entity."""
    entity = SchedyClimate(
        hass=mock_hass,
        room_name="Living Room",
        climate_entity_ids=["climate.living_room_heater"],
        rescheduling_delay=60,
        schedule={
            CONF_DEFAULT_TEMP: 18.0,
            CONF_DAY_TEMP: 21.0,
            CONF_NIGHT_TEMP: 18.0,
            CONF_DAY_START: "07:00",
            CONF_DAY_END: "21:00",
            CONF_USE_WEEKEND_SCHEDULE: False,
        },
    )
    return entity


class TestRuleEvaluation:
    """Test schedule rule evaluation."""

    def test_plunge_pricing(self, mock_climate_entity):
        """Test plunge pricing rule."""
        mock_climate_entity._octopus_price = "Plunge"
        assert mock_climate_entity._evaluate_rules() == 21.0

    def test_room_override(self, mock_climate_entity):
        """Test room override rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "on"
        assert mock_climate_entity._evaluate_rules() == 20.0

    def test_mandj_away(self, mock_climate_entity):
        """Test everyone away rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "not_home"
        assert mock_climate_entity._evaluate_rules() == 18.0

    def test_doors_open(self, mock_climate_entity):
        """Test doors open rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "on"
        assert mock_climate_entity._evaluate_rules() == 17.0

    def test_summer(self, mock_climate_entity):
        """Test summer rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "off"
        mock_climate_entity._heating_season = "Summer"
        assert mock_climate_entity._evaluate_rules() == 17.0

    def test_bedtime(self, mock_climate_entity):
        """Test bedtime rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "off"
        mock_climate_entity._heating_season = "Winter"
        mock_climate_entity._heating_bedtime = "on"
        assert mock_climate_entity._evaluate_rules() == 18.0

    def test_early_bedtime_mode(self, mock_climate_entity):
        """Test early bedtime mode rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "off"
        mock_climate_entity._heating_season = "Winter"
        mock_climate_entity._heating_bedtime = "off"
        mock_climate_entity._heating_mode = "Early Bedtime"
        assert mock_climate_entity._evaluate_rules() == 18.0

    def test_holiday_mode(self, mock_climate_entity):
        """Test holiday mode rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "off"
        mock_climate_entity._heating_season = "Winter"
        mock_climate_entity._heating_bedtime = "off"
        mock_climate_entity._heating_mode = "Holiday"
        assert mock_climate_entity._evaluate_rules() == 17.0

    def test_away_mode(self, mock_climate_entity):
        """Test away mode rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "off"
        mock_climate_entity._heating_season = "Winter"
        mock_climate_entity._heating_bedtime = "off"
        mock_climate_entity._heating_mode = "Away"
        assert mock_climate_entity._evaluate_rules() == 17.0

    def test_peak_pricing(self, mock_climate_entity):
        """Test peak pricing rule."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "off"
        mock_climate_entity._heating_season = "Winter"
        mock_climate_entity._heating_bedtime = "off"
        mock_climate_entity._heating_mode = "Home"
        mock_climate_entity._octopus_price = "Peak"
        assert mock_climate_entity._evaluate_rules() == 18.0

    def test_christmas_mode_daytime(self, mock_climate_entity):
        """Test Christmas mode during daytime."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "off"
        mock_climate_entity._heating_season = "Winter"
        mock_climate_entity._heating_bedtime = "off"
        mock_climate_entity._heating_mode = "Christmas"

        with patch("custom_components.schedy_heating.climate.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 12, 25, 12, 0)  # Noon
            assert mock_climate_entity._evaluate_rules() == 22.0

    def test_christmas_mode_nighttime(self, mock_climate_entity):
        """Test Christmas mode during nighttime."""
        mock_climate_entity._octopus_price = "Normal"
        mock_climate_entity._override_state = "off"
        mock_climate_entity._mandj_location = "home"
        mock_climate_entity._door_status = "off"
        mock_climate_entity._heating_season = "Winter"
        mock_climate_entity._heating_bedtime = "off"
        mock_climate_entity._heating_mode = "Christmas"

        with patch("custom_components.schedy_heating.climate.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 12, 25, 23, 0)  # 11 PM
            assert mock_climate_entity._evaluate_rules() == 18.0


class TestTimeSchedule:
    """Test time-based schedule evaluation."""

    def test_weekday_daytime(self, mock_climate_entity):
        """Test weekday daytime schedule."""
        with patch("custom_components.schedy_heating.climate.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 12, 0)  # Monday noon
            mock_dt.now.return_value.weekday.return_value = 0  # Monday

            result = mock_climate_entity._evaluate_time_schedule()
            assert result == 21.0

    def test_weekday_nighttime(self, mock_climate_entity):
        """Test weekday nighttime schedule."""
        with patch("custom_components.schedy_heating.climate.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 22, 0)  # Monday 10 PM
            mock_dt.now.return_value.weekday.return_value = 0  # Monday

            result = mock_climate_entity._evaluate_time_schedule()
            assert result == 18.0

    def test_weekend_without_weekend_schedule(self, mock_climate_entity):
        """Test weekend without separate weekend schedule."""
        mock_climate_entity._schedule[CONF_USE_WEEKEND_SCHEDULE] = False

        with patch("custom_components.schedy_heating.climate.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 13, 12, 0)  # Saturday noon
            mock_dt.now.return_value.weekday.return_value = 5  # Saturday

            result = mock_climate_entity._evaluate_time_schedule()
            assert result == 21.0  # Uses weekday schedule

    def test_weekend_with_weekend_schedule(self, mock_climate_entity):
        """Test weekend with separate weekend schedule."""
        mock_climate_entity._schedule[CONF_USE_WEEKEND_SCHEDULE] = True
        mock_climate_entity._schedule[CONF_WEEKEND_DAY_TEMP] = 22.0
        mock_climate_entity._schedule[CONF_WEEKEND_NIGHT_TEMP] = 19.0
        mock_climate_entity._schedule[CONF_WEEKEND_DAY_START] = "08:00"
        mock_climate_entity._schedule[CONF_WEEKEND_DAY_END] = "20:00"

        with patch("custom_components.schedy_heating.climate.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 13, 12, 0)  # Saturday noon
            mock_dt.now.return_value.weekday.return_value = 5  # Saturday

            result = mock_climate_entity._evaluate_time_schedule()
            assert result == 22.0


class TestManualOverride:
    """Test manual override functionality."""

    def test_set_temperature_creates_override(self, mock_climate_entity):
        """Test that setting temperature creates a manual override."""
        mock_climate_entity._attr_target_temperature = 18.0

        mock_climate_entity.async_set_temperature(temperature=22.0)

        assert mock_climate_entity._manual_override is True
        assert mock_climate_entity._attr_target_temperature == 22.0
        assert mock_climate_entity._manual_override_until is not None

    def test_override_protected_during_delay(self, mock_climate_entity):
        """Test that override is protected during rescheduling delay."""
        # Set override
        mock_climate_entity._manual_override = True
        mock_climate_entity._manual_override_until = datetime.now() + timedelta(
            minutes=60
        )
        mock_climate_entity._attr_target_temperature = 22.0

        # Try to evaluate schedule
        mock_climate_entity._heating_mode = "Home"
        mock_climate_entity._evaluate_rules = MagicMock(return_value=18.0)

        # Should not change temperature during override
        mock_climate_entity._evaluate_rules.return_value = 18.0
        mock_climate_entity._async_evaluate_schedule()

        assert mock_climate_entity._attr_target_temperature == 22.0

    def test_override_expires(self, mock_climate_entity):
        """Test that override expires after delay."""
        # Set expired override
        mock_climate_entity._manual_override = True
        mock_climate_entity._manual_override_until = datetime.now() - timedelta(
            minutes=1
        )
        mock_climate_entity._attr_target_temperature = 22.0

        # Mock evaluate_rules to return a different temp
        with patch.object(mock_climate_entity, "_evaluate_rules", return_value=18.0):
            mock_climate_entity._async_evaluate_schedule()

        assert mock_climate_entity._manual_override is False
        assert mock_climate_entity._attr_target_temperature == 18.0


class TestPresenceDetection:
    """Test presence detection logic."""

    def test_mandj_both_home(self, mock_climate_entity, mock_hass):
        """Test when both Matthew and Jenny are home."""
        mock_matthew = MagicMock()
        mock_matthew.state = "home"
        mock_jenny = MagicMock()
        mock_jenny.state = "home"

        mock_hass.states.get.side_effect = lambda eid: {
            "person.matthew": mock_matthew,
            "person.jenny": mock_jenny,
        }.get(eid)

        mock_climate_entity._async_update_presence_sync()

        assert mock_climate_entity._mandj_location == "home"

    def test_mandj_both_away(self, mock_climate_entity, mock_hass):
        """Test when both Matthew and Jenny are away."""
        mock_matthew = MagicMock()
        mock_matthew.state = "not_home"
        mock_jenny = MagicMock()
        mock_jenny.state = "not_home"

        mock_hass.states.get.side_effect = lambda eid: {
            "person.matthew": mock_matthew,
            "person.jenny": mock_jenny,
        }.get(eid)

        mock_climate_entity._async_update_presence_sync()

        assert mock_climate_entity._mandj_location == "not_home"

    def test_mandj_one_away(self, mock_climate_entity, mock_hass):
        """Test when one person is away."""
        mock_matthew = MagicMock()
        mock_matthew.state = "home"
        mock_jenny = MagicMock()
        mock_jenny.state = "not_home"

        mock_hass.states.get.side_effect = lambda eid: {
            "person.matthew": mock_matthew,
            "person.jenny": mock_jenny,
        }.get(eid)

        mock_climate_entity._async_update_presence_sync()

        assert mock_climate_entity._mandj_location == "home"


class TestExtraStateAttributes:
    """Test extra state attributes."""

    def test_attributes_include_schedule(self, mock_climate_entity):
        """Test that attributes include schedule config."""
        attrs = mock_climate_entity.extra_state_attributes
        assert "schedule" in attrs
        assert attrs["schedule"]["day_temp"] == 21.0

    def test_attributes_include_octopus_info(self, mock_climate_entity):
        """Test that attributes include Octopus Energy info."""
        mock_climate_entity._octopus_coordinator = MagicMock()
        mock_climate_entity._octopus_coordinator.has_octopus_energy = True
        mock_climate_entity._octopus_coordinator.rate_sensor_id = "sensor.octopus_rate"
        mock_climate_entity._octopus_coordinator.saving_sensor_id = (
            "binary_sensor.octopus_saving"
        )
        mock_climate_entity._octopus_coordinator.get_current_rate.return_value = 15.5
        mock_climate_entity._octopus_coordinator.is_saving_session_active.return_value = (
            False
        )

        attrs = mock_climate_entity.extra_state_attributes

        assert attrs["octopus_energy_detected"] is True
        assert attrs["octopus_rate_sensor"] == "sensor.octopus_rate"
        assert attrs["octopus_current_rate"] == 15.5
        assert attrs["octopus_saving_session_active"] is False

    def test_attributes_without_octopus(self, mock_climate_entity):
        """Test attributes without Octopus Energy."""
        mock_climate_entity._octopus_coordinator = None

        attrs = mock_climate_entity.extra_state_attributes

        assert attrs["octopus_energy_detected"] is False
