"""Binary sensor entities for Schedy Heating."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ROOMS, CONF_ROOM_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities for room overrides."""
    rooms = entry.data.get(CONF_ROOMS, [])
    entities = []

    for room in rooms:
        room_name = room[CONF_ROOM_NAME]
        entities.append(RoomOverrideSensor(room_name))

    async_add_entities(entities)


class RoomOverrideSensor(BinarySensorEntity):
    """Binary sensor for room override status."""

    _attr_device_class = "running"
    _attr_is_on = False
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, room_name: str) -> None:
        """Initialize the sensor."""
        self._room_name = room_name
        self._attr_name = f"{room_name} Override"
        self._attr_unique_id = f"{DOMAIN}_{room_name}_override"

    async def async_turn_on(self) -> None:
        """Turn on the override."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the override."""
        self._attr_is_on = False
        self.async_write_ha_state()
