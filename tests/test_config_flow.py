"""Tests for Schedy Heating config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.schedy_heating.config_flow import SchedyHeatingConfigFlow
from custom_components.schedy_heating.const import (
    CONF_CLIMATE_ENTITIES,
    CONF_OCTOPUS_ENABLED,
    CONF_OCTOPUS_RATE_SENSOR,
    CONF_OCTOPUS_SAVING_SENSOR,
    CONF_ROOMS,
    CONF_ROOM_NAME,
    CONF_SCHEDULE,
    CONF_RESCHEDULING_DELAY,
    DOMAIN,
)


@pytest.fixture
def config_flow(hass: HomeAssistant) -> SchedyHeatingConfigFlow:
    """Create a config flow instance."""
    flow = SchedyHeatingConfigFlow()
    flow.hass = hass
    return flow


class TestUserStep:
    """Test the user step of the config flow."""

    async def test_user_step_show_form(self, config_flow):
        """Test that user step shows form."""
        result = await config_flow.async_step_user()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

    async def test_user_step_with_climate_entities(self, config_flow):
        """Test user step with climate entities selected."""
        result = await config_flow.async_step_user(
            {CONF_CLIMATE_ENTITIES: ["climate.living_room"]}
        )

        # Should proceed to octopus step
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "octopus"


class TestOctopusStep:
    """Test the Octopus Energy step of the config flow."""

    async def test_octopus_step_skip_when_not_detected(self, config_flow):
        """Test that octopus step is skipped when Octopus Energy is not installed."""
        config_flow._climate_entities = ["climate.living_room"]

        with patch(
            "custom_components.schedy_heating.config_flow.detect_octopus_energy"
        ) as mock_detect:
            mock_detect.return_value = {"has_octopus_energy": False}
            result = await config_flow.async_step_octopus()

        # Should skip to rooms step
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "rooms"

    async def test_octopus_step_show_form_when_detected(self, config_flow):
        """Test that octopus step shows form when Octopus Energy is installed."""
        config_flow._climate_entities = ["climate.living_room"]

        with patch(
            "custom_components.schedy_heating.config_flow.detect_octopus_energy"
        ) as mock_detect:
            mock_detect.return_value = {
                "has_octopus_energy": True,
                "rate_sensors": ["sensor.octopus_rate"],
                "saving_session_sensors": ["binary_sensor.octopus_saving"],
            }
            result = await config_flow.async_step_octopus()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "octopus"

    async def test_octopus_step_enable(self, config_flow):
        """Test enabling Octopus Energy integration."""
        config_flow._climate_entities = ["climate.living_room"]

        with patch(
            "custom_components.schedy_heating.config_flow.detect_octopus_energy"
        ) as mock_detect:
            mock_detect.return_value = {
                "has_octopus_energy": True,
                "rate_sensors": ["sensor.octopus_rate"],
                "saving_session_sensors": ["binary_sensor.octopus_saving"],
            }
            result = await config_flow.async_step_octopus(
                {
                    CONF_OCTOPUS_ENABLED: True,
                    CONF_OCTOPUS_RATE_SENSOR: "sensor.octopus_rate",
                    CONF_OCTOPUS_SAVING_SENSOR: "binary_sensor.octopus_saving",
                }
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "rooms"
        assert config_flow._octopus_enabled is True
        assert config_flow._octopus_rate_sensor == "sensor.octopus_rate"
        assert config_flow._octopus_saving_sensor == "binary_sensor.octopus_saving"

    async def test_octopus_step_disable(self, config_flow):
        """Test disabling Octopus Energy integration."""
        config_flow._climate_entities = ["climate.living_room"]

        with patch(
            "custom_components.schedy_heating.config_flow.detect_octopus_energy"
        ) as mock_detect:
            mock_detect.return_value = {
                "has_octopus_energy": True,
                "rate_sensors": ["sensor.octopus_rate"],
                "saving_session_sensors": ["binary_sensor.octopus_saving"],
            }
            result = await config_flow.async_step_octopus(
                {CONF_OCTOPUS_ENABLED: False}
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "rooms"
        assert config_flow._octopus_enabled is False


class TestRoomsStep:
    """Test the rooms step of the config flow."""

    async def test_rooms_step_show_form(self, config_flow):
        """Test that rooms step shows form."""
        result = await config_flow.async_step_rooms()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "rooms"

    async def test_rooms_step_add_room(self, config_flow):
        """Test adding a room."""
        result = await config_flow.async_step_rooms(
            {
                "room_name": "Living Room",
                "room_climate_entities": ["climate.living_room_heater"],
                "rescheduling_delay": 60,
                "add_another": True,
                "finish": False,
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "rooms"
        assert len(config_flow._rooms) == 1
        assert config_flow._rooms[0]["name"] == "Living Room"

    async def test_rooms_step_finish(self, config_flow):
        """Test finishing rooms step."""
        result = await config_flow.async_step_rooms(
            {
                "room_name": "Living Room",
                "room_climate_entities": ["climate.living_room_heater"],
                "rescheduling_delay": 60,
                "add_another": False,
                "finish": True,
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "schedule"

    async def test_rooms_step_no_rooms_error(self, config_flow):
        """Test error when no rooms added."""
        # First call to set finish without adding any rooms
        config_flow._rooms = []
        result = await config_flow.async_step_rooms(
            {
                "room_name": "",
                "add_another": False,
                "finish": True,
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "rooms"
        assert result["errors"] == {"base": "no_rooms"}


class TestScheduleStep:
    """Test the schedule step of the config flow."""

    async def test_schedule_step_show_form(self, config_flow):
        """Test that schedule step shows form."""
        config_flow._rooms = [{"name": "Living Room", "climate_entities": []}]
        config_flow._current_room_idx = 0

        result = await config_flow.async_step_schedule()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "schedule"

    async def test_schedule_step_configure(self, config_flow):
        """Test configuring a schedule."""
        config_flow._rooms = [
            {
                "name": "Living Room",
                "climate_entities": ["climate.living_room_heater"],
            }
        ]
        config_flow._current_room_idx = 0

        result = await config_flow.async_step_schedule(
            {
                "default_temp": 18.0,
                "day_temp": 21.0,
                "night_temp": 18.0,
                "day_start": "07:00",
                "day_end": "21:00",
                "use_weekend_schedule": False,
            }
        )

        # Should create entry since only one room
        assert result["type"] == FlowResultType.CREATE_ENTRY

    async def test_schedule_step_multiple_rooms(self, config_flow):
        """Test configuring schedules for multiple rooms."""
        config_flow._rooms = [
            {"name": "Living Room", "climate_entities": ["climate.living_room_heater"]},
            {"name": "Bedroom", "climate_entities": ["climate.bedroom_heater"]},
        ]
        config_flow._current_room_idx = 0

        # Configure first room
        result = await config_flow.async_step_schedule(
            {
                "default_temp": 18.0,
                "day_temp": 21.0,
                "night_temp": 18.0,
                "day_start": "07:00",
                "day_end": "21:00",
                "use_weekend_schedule": False,
            }
        )

        # Should show form for second room
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "schedule"
        assert config_flow._current_room_idx == 1

    async def test_schedule_step_with_weekend(self, config_flow):
        """Test configuring schedule with weekend settings."""
        config_flow._rooms = [{"name": "Living Room", "climate_entities": []}]
        config_flow._current_room_idx = 0

        result = await config_flow.async_step_schedule(
            {
                "default_temp": 18.0,
                "day_temp": 21.0,
                "night_temp": 18.0,
                "day_start": "07:00",
                "day_end": "21:00",
                "use_weekend_schedule": True,
                "weekend_day_temp": 22.0,
                "weekend_night_temp": 19.0,
                "weekend_day_start": "08:00",
                "weekend_day_end": "20:00",
            }
        )

        # Check that weekend schedule was stored
        schedule = config_flow._rooms[0].get(CONF_SCHEDULE, {})
        assert schedule.get("use_weekend_schedule") is True
        assert schedule.get("weekend_day_temp") == 22.0


class TestCreateEntry:
    """Test entry creation."""

    async def test_create_entry_basic(self, config_flow):
        """Test creating a basic config entry."""
        config_flow._climate_entities = ["climate.living_room"]
        config_flow._rooms = [
            {
                "name": "Living Room",
                "climate_entities": ["climate.living_room_heater"],
                "rescheduling_delay": 60,
            }
        ]
        config_flow._octopus_enabled = False

        result = config_flow._create_entry()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Schedy Heating"
        assert CONF_CLIMATE_ENTITIES in result["data"]
        assert CONF_ROOMS in result["data"]

    async def test_create_entry_with_octopus(self, config_flow):
        """Test creating config entry with Octopus Energy."""
        config_flow._climate_entities = ["climate.living_room"]
        config_flow._rooms = [
            {
                "name": "Living Room",
                "climate_entities": ["climate.living_room_heater"],
                "rescheduling_delay": 60,
            }
        ]
        config_flow._octopus_enabled = True
        config_flow._octopus_rate_sensor = "sensor.octopus_rate"
        config_flow._octopus_saving_sensor = "binary_sensor.octopus_saving"

        result = config_flow._create_entry()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_OCTOPUS_ENABLED] is True
        assert result["data"][CONF_OCTOPUS_RATE_SENSOR] == "sensor.octopus_rate"
        assert (
            result["data"][CONF_OCTOPUS_SAVING_SENSOR]
            == "binary_sensor.octopus_saving"
        )
