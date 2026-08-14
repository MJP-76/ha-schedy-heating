"""Config flow for Schedy Heating integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CLIMATE_ENTITIES,
    CONF_OVERRIDE_ENTITY,
    CONF_PRESENCE_ENTITY,
    CONF_RESCHEDULING_DELAY,
    CONF_ROOMS,
    CONF_ROOM_NAME,
    DEFAULT_RESCHEDULING_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SchedyHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Schedy Heating."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._rooms: list[dict[str, Any]] = []
        self._climate_entities: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Select climate entities to manage."""
        if user_input is not None:
            self._climate_entities = user_input["climate_entities"]
            return await self.async_step_rooms()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("climate_entities"): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="climate",
                            multiple=True,
                        )
                    ),
                }
            ),
        )

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Configure rooms."""
        if user_input is not None:
            if user_input.get("add_another"):
                self._rooms.append(self._build_room(user_input))
                return await self.async_step_rooms()

            if user_input.get("finish"):
                if not self._rooms:
                    return self.async_show_form(
                        step_id="rooms",
                        data_schema=self._room_schema(),
                        errors={"base": "no_rooms"},
                    )
                return self._create_entry()

        return self.async_show_form(
            step_id="rooms",
            data_schema=self._room_schema(),
        )

    def _build_room(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Build a room config dict from user input."""
        room: dict[str, Any] = {
            "name": user_input["room_name"],
            "climate_entities": user_input.get("room_climate_entities", []),
            "rescheduling_delay": user_input.get(
                "rescheduling_delay", DEFAULT_RESCHEDULING_DELAY
            ),
        }
        if user_input.get("override_entity"):
            room["override_entity"] = user_input["override_entity"]
        if user_input.get("presence_entity"):
            room["presence_entity"] = user_input["presence_entity"]
        return room

    def _room_schema(self) -> vol.Schema:
        """Return the room configuration schema."""
        return vol.Schema(
            {
                vol.Optional("room_name"): str,
                vol.Optional("room_climate_entities"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="climate",
                        multiple=True,
                    )
                ),
                vol.Optional(
                    "rescheduling_delay", default=DEFAULT_RESCHEDULING_DELAY
                ): vol.All(int, vol.Range(min=0, max=1440)),
                vol.Optional("override_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="input_boolean",
                    )
                ),
                vol.Optional("presence_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="person",
                    )
                ),
                vol.Optional("add_another", default=False): bool,
                vol.Optional("finish", default=True): bool,
            }
        )

    def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title="Schedy Heating",
            data={
                "climate_entities": self._climate_entities,
                CONF_ROOMS: self._rooms,
            },
        )
