"""Octopus Energy auto-detection for Schedy Heating."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Octopus Energy entity patterns
OCTOPUS_RATE_SENSOR_PATTERN = "sensor.octopus_energy_electricity_"
OCTOPUS_SAVING_SESSION_PATTERN = "binary_sensor.octopus_energy_"
OCTOPUS_SAVING_SESSION_SUFFIX = "_octoplus_saving_sessions"

# Price tier thresholds (p/kWh)
# These are typical Agile thresholds - adjust as needed
PLUNGE_THRESHOLD = 0.0  # Free or negative
PEAK_THRESHOLD = 30.0  # Above 30p is peak


def detect_octopus_energy(hass: HomeAssistant) -> dict[str, Any]:
    """Detect Octopus Energy entities in the installation.

    Returns:
        Dict with detected entities:
        - rate_sensors: list of electricity rate sensor entity_ids
        - saving_session_sensors: list of saving session sensor entity_ids
        - has_octopus_energy: bool indicating if integration is detected
    """
    result = {
        "has_octopus_energy": False,
        "rate_sensors": [],
        "saving_session_sensors": [],
    }

    # Check for Octopus Energy entities
    for entity_id in hass.states.async_entity_ids():
        if entity_id.startswith(OCTOPUS_RATE_SENSOR_PATTERN):
            result["rate_sensors"].append(entity_id)
            result["has_octopus_energy"] = True
        elif (
            entity_id.startswith(OCTOPUS_SAVING_SESSION_PATTERN)
            and entity_id.endswith(OCTOPUS_SAVING_SESSION_SUFFIX)
        ):
            result["saving_session_sensors"].append(entity_id)
            result["has_octopus_energy"] = True

    return result


def get_price_tier_from_rate(rate_pence: float) -> str:
    """Determine price tier from electricity rate in pence/kWh.

    Args:
        rate_pence: Current electricity rate in pence per kWh

    Returns:
        Price tier: "Plunge", "Peak", or "Normal"
    """
    if rate_pence <= PLUNGE_THRESHOLD:
        return "Plunge"
    elif rate_pence >= PEAK_THRESHOLD:
        return "Peak"
    return "Normal"


def get_current_octopus_rate(hass: HomeAssistant, rate_sensor_id: str) -> float | None:
    """Get the current Octopus Energy rate from a sensor.

    Args:
        hass: HomeAssistant instance
        rate_sensor_id: Entity ID of the rate sensor

    Returns:
        Current rate in pence/kWh, or None if unavailable
    """
    state = hass.states.get(rate_sensor_id)
    if state is None or state.state in ("unknown", "unavailable"):
        return None

    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


def is_saving_session_active(
    hass: HomeAssistant, saving_sensor_id: str
) -> bool:
    """Check if an Octopus Energy saving session is active.

    Args:
        hass: HomeAssistant instance
        saving_sensor_id: Entity ID of the saving session sensor

    Returns:
        True if saving session is active
    """
    state = hass.states.get(saving_sensor_id)
    if state is None:
        return False
    return state.state == "on"


class OctopusEnergyCoordinator:
    """Coordinator for Octopus Energy data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        self._hass = hass
        self._detected = detect_octopus_energy(hass)
        self._rate_sensor_id: str | None = None
        self._saving_sensor_id: str | None = None

        # Auto-select the first rate sensor if available
        if self._detected["rate_sensors"]:
            self._rate_sensor_id = self._detected["rate_sensors"][0]
            _LOGGER.info(
                "Auto-detected Octopus Energy rate sensor: %s",
                self._rate_sensor_id,
            )

        # Auto-select the first saving session sensor if available
        if self._detected["saving_session_sensors"]:
            self._saving_sensor_id = self._detected["saving_session_sensors"][0]
            _LOGGER.info(
                "Auto-detected Octopus Energy saving session sensor: %s",
                self._saving_sensor_id,
            )

    @property
    def has_octopus_energy(self) -> bool:
        """Return True if Octopus Energy is detected."""
        return self._detected["has_octopus_energy"]

    @property
    def rate_sensor_id(self) -> str | None:
        """Return the rate sensor entity ID."""
        return self._rate_sensor_id

    @property
    def saving_sensor_id(self) -> str | None:
        """Return the saving session sensor entity ID."""
        return self._saving_sensor_id

    @property
    def detected_entities(self) -> dict[str, Any]:
        """Return all detected entities."""
        return self._detected

    def get_current_price_tier(self) -> str:
        """Get the current price tier based on Octopus Energy data.

        Returns:
            Price tier: "Plunge", "Peak", or "Normal"
        """
        if not self._rate_sensor_id:
            return "Normal"

        rate = get_current_octopus_rate(self._hass, self._rate_sensor_id)
        if rate is None:
            return "Normal"

        return get_price_tier_from_rate(rate)

    def is_saving_session_active(self) -> bool:
        """Check if a saving session is currently active.

        Returns:
            True if saving session is active
        """
        if not self._saving_sensor_id:
            return False

        return is_saving_session_active(self._hass, self._saving_sensor_id)

    def get_current_rate(self) -> float | None:
        """Get the current electricity rate.

        Returns:
            Current rate in pence/kWh, or None if unavailable
        """
        if not self._rate_sensor_id:
            return None

        return get_current_octopus_rate(self._hass, self._rate_sensor_id)
