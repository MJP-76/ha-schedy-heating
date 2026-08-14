"""The Schedy Heating integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_OCTOPUS_ENABLED,
    CONF_OCTOPUS_RATE_SENSOR,
    CONF_OCTOPUS_SAVING_SENSOR,
    DOMAIN,
    PLATFORMS,
)
from .octopus import OctopusEnergyCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Schedy Heating from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize Octopus Energy coordinator
    octopus_coordinator = OctopusEnergyCoordinator(hass)

    # Override auto-detection with configured entities if available
    octopus_enabled = entry.data.get(CONF_OCTOPUS_ENABLED, True)
    if octopus_enabled:
        configured_rate_sensor = entry.data.get(CONF_OCTOPUS_RATE_SENSOR)
        configured_saving_sensor = entry.data.get(CONF_OCTOPUS_SAVING_SENSOR)

        if configured_rate_sensor:
            octopus_coordinator.set_rate_sensor(configured_rate_sensor)
        if configured_saving_sensor:
            octopus_coordinator.set_saving_sensor(configured_saving_sensor)

    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "octopus_coordinator": octopus_coordinator,
    }

    if octopus_coordinator.has_octopus_energy:
        _LOGGER.info(
            "Octopus Energy configured - rate sensor: %s, saving session: %s",
            octopus_coordinator.rate_sensor_id,
            octopus_coordinator.saving_sensor_id,
        )
    else:
        _LOGGER.info("Octopus Energy not configured - using manual price selection")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
