"""The Schedy Heating integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .octopus import OctopusEnergyCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Schedy Heating from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize Octopus Energy coordinator
    octopus_coordinator = OctopusEnergyCoordinator(hass)
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "octopus_coordinator": octopus_coordinator,
    }

    if octopus_coordinator.has_octopus_energy:
        _LOGGER.info(
            "Octopus Energy detected - rate sensor: %s, saving session: %s",
            octopus_coordinator.rate_sensor_id,
            octopus_coordinator.saving_sensor_id,
        )
    else:
        _LOGGER.info("Octopus Energy not detected - using manual price selection")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
