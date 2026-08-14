"""Standalone tests for Octopus Energy integration.

These tests mock the homeassistant module so they can run without
the full HA installation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock homeassistant modules before importing
sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.entity"] = MagicMock()
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.climate"] = MagicMock()
sys.modules["homeassistant.components.select"] = MagicMock()
sys.modules["homeassistant.components.binary_sensor"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["homeassistant.data_entry_flow"] = MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
sys.modules["homeassistant.helpers.event"] = MagicMock()
sys.modules["homeassistant.helpers.typing"] = MagicMock()
sys.modules["voluptuous"] = MagicMock()

from custom_components.schedy_heating.octopus import (
    OctopusEnergyCoordinator,
    detect_octopus_energy,
    get_current_octopus_rate,
    get_price_tier_from_rate,
    is_saving_session_active,
)


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.states = MagicMock()
    hass.states.async_all = MagicMock(return_value=[])
    hass.states.async_entity_ids = MagicMock(return_value=[])
    hass.states.get = MagicMock(return_value=None)
    return hass


class TestPriceTierCalculation:
    """Test price tier calculation from rates."""

    def test_plunge_price_negative(self):
        """Test plunge price detection with negative rate."""
        assert get_price_tier_from_rate(-5.0) == "Plunge"

    def test_plunge_price_zero(self):
        """Test plunge price detection with zero rate."""
        assert get_price_tier_from_rate(0.0) == "Plunge"

    def test_peak_price_threshold(self):
        """Test peak price detection at threshold."""
        assert get_price_tier_from_rate(30.0) == "Peak"

    def test_peak_price_above_threshold(self):
        """Test peak price detection above threshold."""
        assert get_price_tier_from_rate(50.0) == "Peak"

    def test_normal_price_mid_range(self):
        """Test normal price detection in mid range."""
        assert get_price_tier_from_rate(15.0) == "Normal"

    def test_normal_price_near_peak(self):
        """Test normal price detection near peak threshold."""
        assert get_price_tier_from_rate(29.9) == "Normal"


class TestDetectOctopusEnergy:
    """Test Octopus Energy entity detection."""

    def test_detect_rate_sensors(self, mock_hass):
        """Test detection of rate sensors."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.octopus_energy_electricity_abc123_current_rate",
            "sensor.other_entity",
        ]

        result = detect_octopus_energy(mock_hass)

        assert result["has_octopus_energy"] is True
        assert len(result["rate_sensors"]) == 1
        assert (
            "sensor.octopus_energy_electricity_abc123_current_rate"
            in result["rate_sensors"]
        )

    def test_detect_saving_sensors(self, mock_hass):
        """Test detection of saving session sensors."""
        mock_hass.states.async_entity_ids.return_value = [
            "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions",
        ]

        result = detect_octopus_energy(mock_hass)

        assert result["has_octopus_energy"] is True
        assert len(result["saving_session_sensors"]) == 1

    def test_detect_both_sensors(self, mock_hass):
        """Test detection of both sensor types."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.octopus_energy_electricity_abc123_current_rate",
            "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions",
        ]

        result = detect_octopus_energy(mock_hass)

        assert result["has_octopus_energy"] is True
        assert len(result["rate_sensors"]) == 1
        assert len(result["saving_session_sensors"]) == 1

    def test_no_octopus_energy(self, mock_hass):
        """Test when Octopus Energy is not installed."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.other_entity",
            "light.living_room",
        ]

        result = detect_octopus_energy(mock_hass)

        assert result["has_octopus_energy"] is False
        assert len(result["rate_sensors"]) == 0
        assert len(result["saving_session_sensors"]) == 0


class TestGetCurrentOctopusRate:
    """Test getting current rate from sensor."""

    def test_valid_rate(self, mock_hass):
        """Test getting a valid rate."""
        mock_state = MagicMock()
        mock_state.state = "15.5"
        mock_hass.states.get.return_value = mock_state

        rate = get_current_octopus_rate(
            mock_hass, "sensor.octopus_energy_electricity_abc123_current_rate"
        )

        assert rate == 15.5

    def test_unavailable_rate(self, mock_hass):
        """Test getting rate when sensor is unavailable."""
        mock_state = MagicMock()
        mock_state.state = "unavailable"
        mock_hass.states.get.return_value = mock_state

        rate = get_current_octopus_rate(
            mock_hass, "sensor.octopus_energy_electricity_abc123_current_rate"
        )

        assert rate is None

    def test_unknown_rate(self, mock_hass):
        """Test getting rate when sensor is unknown."""
        mock_state = MagicMock()
        mock_state.state = "unknown"
        mock_hass.states.get.return_value = mock_state

        rate = get_current_octopus_rate(
            mock_hass, "sensor.octopus_energy_electricity_abc123_current_rate"
        )

        assert rate is None

    def test_invalid_rate(self, mock_hass):
        """Test getting rate with invalid value."""
        mock_state = MagicMock()
        mock_state.state = "invalid"
        mock_hass.states.get.return_value = mock_state

        rate = get_current_octopus_rate(
            mock_hass, "sensor.octopus_energy_electricity_abc123_current_rate"
        )

        assert rate is None

    def test_missing_sensor(self, mock_hass):
        """Test getting rate when sensor doesn't exist."""
        mock_hass.states.get.return_value = None

        rate = get_current_octopus_rate(
            mock_hass, "sensor.octopus_energy_electricity_abc123_current_rate"
        )

        assert rate is None


class TestIsSavingSessionActive:
    """Test saving session detection."""

    def test_saving_session_active(self, mock_hass):
        """Test when saving session is active."""
        mock_state = MagicMock()
        mock_state.state = "on"
        mock_hass.states.get.return_value = mock_state

        assert (
            is_saving_session_active(
                mock_hass,
                "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions",
            )
            is True
        )

    def test_saving_session_inactive(self, mock_hass):
        """Test when saving session is inactive."""
        mock_state = MagicMock()
        mock_state.state = "off"
        mock_hass.states.get.return_value = mock_state

        assert (
            is_saving_session_active(
                mock_hass,
                "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions",
            )
            is False
        )

    def test_missing_sensor(self, mock_hass):
        """Test when sensor doesn't exist."""
        mock_hass.states.get.return_value = None

        assert (
            is_saving_session_active(
                mock_hass,
                "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions",
            )
            is False
        )


class TestOctopusEnergyCoordinator:
    """Test OctopusEnergyCoordinator."""

    def test_init_with_octopus(self, mock_hass):
        """Test initialization with Octopus Energy installed."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.octopus_energy_electricity_abc123_current_rate",
            "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions",
        ]

        coordinator = OctopusEnergyCoordinator(mock_hass)

        assert coordinator.has_octopus_energy is True
        assert (
            coordinator.rate_sensor_id
            == "sensor.octopus_energy_electricity_abc123_current_rate"
        )
        assert (
            coordinator.saving_sensor_id
            == "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions"
        )

    def test_init_without_octopus(self, mock_hass):
        """Test initialization without Octopus Energy."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.other_entity",
        ]

        coordinator = OctopusEnergyCoordinator(mock_hass)

        assert coordinator.has_octopus_energy is False
        assert coordinator.rate_sensor_id is None
        assert coordinator.saving_sensor_id is None

    def test_set_rate_sensor(self, mock_hass):
        """Test overriding rate sensor."""
        mock_hass.states.async_entity_ids.return_value = []
        coordinator = OctopusEnergyCoordinator(mock_hass)

        coordinator.set_rate_sensor("sensor.custom_rate_sensor")

        assert coordinator.rate_sensor_id == "sensor.custom_rate_sensor"

    def test_set_saving_sensor(self, mock_hass):
        """Test overriding saving sensor."""
        mock_hass.states.async_entity_ids.return_value = []
        coordinator = OctopusEnergyCoordinator(mock_hass)

        coordinator.set_saving_sensor("sensor.custom_saving_sensor")

        assert coordinator.saving_sensor_id == "sensor.custom_saving_sensor"

    def test_get_price_tier_normal(self, mock_hass):
        """Test getting normal price tier."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.octopus_energy_electricity_abc123_current_rate",
        ]
        coordinator = OctopusEnergyCoordinator(mock_hass)

        mock_state = MagicMock()
        mock_state.state = "15.0"
        mock_hass.states.get.return_value = mock_state

        assert coordinator.get_current_price_tier() == "Normal"

    def test_get_price_tier_plunge(self, mock_hass):
        """Test getting plunge price tier."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.octopus_energy_electricity_abc123_current_rate",
        ]
        coordinator = OctopusEnergyCoordinator(mock_hass)

        mock_state = MagicMock()
        mock_state.state = "-5.0"
        mock_hass.states.get.return_value = mock_state

        assert coordinator.get_current_price_tier() == "Plunge"

    def test_get_price_tier_peak(self, mock_hass):
        """Test getting peak price tier."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.octopus_energy_electricity_abc123_current_rate",
        ]
        coordinator = OctopusEnergyCoordinator(mock_hass)

        mock_state = MagicMock()
        mock_state.state = "35.0"
        mock_hass.states.get.return_value = mock_state

        assert coordinator.get_current_price_tier() == "Peak"

    def test_is_saving_session_active(self, mock_hass):
        """Test checking if saving session is active."""
        mock_hass.states.async_entity_ids.return_value = [
            "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions",
        ]
        coordinator = OctopusEnergyCoordinator(mock_hass)

        mock_state = MagicMock()
        mock_state.state = "on"
        mock_hass.states.get.return_value = mock_state

        assert coordinator.is_saving_session_active() is True

    def test_is_saving_session_inactive(self, mock_hass):
        """Test checking if saving session is inactive."""
        mock_hass.states.async_entity_ids.return_value = [
            "binary_sensor.octopus_energy_a_20a6e4b4_octoplus_saving_sessions",
        ]
        coordinator = OctopusEnergyCoordinator(mock_hass)

        mock_state = MagicMock()
        mock_state.state = "off"
        mock_hass.states.get.return_value = mock_state

        assert coordinator.is_saving_session_active() is False

    def test_get_current_rate(self, mock_hass):
        """Test getting current rate."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.octopus_energy_electricity_abc123_current_rate",
        ]
        coordinator = OctopusEnergyCoordinator(mock_hass)

        mock_state = MagicMock()
        mock_state.state = "15.5"
        mock_hass.states.get.return_value = mock_state

        assert coordinator.get_current_rate() == 15.5

    def test_get_current_rate_no_sensor(self, mock_hass):
        """Test getting current rate with no sensor."""
        mock_hass.states.async_entity_ids.return_value = []
        coordinator = OctopusEnergyCoordinator(mock_hass)

        assert coordinator.get_current_rate() is None

    def test_detected_entities_property(self, mock_hass):
        """Test detected_entities property."""
        mock_hass.states.async_entity_ids.return_value = [
            "sensor.octopus_energy_electricity_abc123_current_rate",
        ]
        coordinator = OctopusEnergyCoordinator(mock_hass)

        detected = coordinator.detected_entities
        assert "rate_sensors" in detected
        assert "saving_session_sensors" in detected
