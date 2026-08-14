"""Select entities for Schedy Heating."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_HEATING_MODE,
    DEFAULT_OCTOPUS_PRICE,
    DEFAULT_SEASON,
    DOMAIN,
    HEATING_MODES,
    OCTOPUS_PRICES,
    SEASONS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for Schedy Heating."""
    async_add_entities(
        [
            HeatingModeSelect(),
            HeatingSeasonSelect(),
            OctopusPriceSelect(),
        ]
    )


class HeatingModeSelect(SelectEntity):
    """Select entity for heating mode."""

    _attr_name = "Heating Mode"
    _attr_options = HEATING_MODES
    _attr_current_option = DEFAULT_HEATING_MODE
    _attr_unique_id = f"{DOMAIN}_heating_mode"
    _attr_icon = "mdi:home-thermometer-outline"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self.async_write_ha_state()


class HeatingSeasonSelect(SelectEntity):
    """Select entity for heating season."""

    _attr_name = "Heating Season"
    _attr_options = SEASONS
    _attr_current_option = DEFAULT_SEASON
    _attr_unique_id = f"{DOMAIN}_heating_season"
    _attr_icon = "mdi:weather-snowy"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self.async_write_ha_state()


class OctopusPriceSelect(SelectEntity):
    """Select entity for Octopus Energy price tier."""

    _attr_name = "Octopus Price"
    _attr_options = OCTOPUS_PRICES
    _attr_current_option = DEFAULT_OCTOPUS_PRICE
    _attr_unique_id = f"{DOMAIN}_octopus_price"
    _attr_icon = "mdi:lightning-bolt"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self.async_write_ha_state()
