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
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_DAY_TEMP,
    CONF_DEFAULT_TEMP,
    CONF_NIGHT_TEMP,
    CONF_OVERRIDE_ENTITY,
    CONF_OCTOPUS_ENABLED,
    CONF_OCTOPUS_RATE_SENSOR,
    CONF_OCTOPUS_SAVING_SENSOR,
    CONF_PRESENCE_ENTITY,
    CONF_RESCHEDULING_DELAY,
    CONF_ROOMS,
    CONF_ROOM_NAME,
    CONF_SCHEDULE,
    CONF_USE_WEEKEND_SCHEDULE,
    CONF_WEEKEND_DAY_END,
    CONF_WEEKEND_DAY_START,
    CONF_WEEKEND_DAY_TEMP,
    CONF_WEEKEND_NIGHT_TEMP,
    DEFAULT_DAY_END,
    DEFAULT_DAY_START,
    DEFAULT_DAY_TEMP,
    DEFAULT_NIGHT_TEMP,
    DEFAULT_RESCHEDULING_DELAY,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
)
from .octopus import detect_octopus_energy

_LOGGER = logging.getLogger(__name__)


class SchedyHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Schedy Heating."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._rooms: list[dict[str, Any]] = []
        self._climate_entities: list[str] = []
        self._current_room_idx: int = 0
        self._octopus_detected: dict[str, Any] = {}
        self._octopus_enabled: bool = False
        self._octopus_rate_sensor: str | None = None
        self._octopus_saving_sensor: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Select climate entities to manage."""
        if user_input is not None:
            self._climate_entities = user_input["climate_entities"]
            return await self.async_step_octopus()

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

    async def async_step_octopus(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Configure Octopus Energy integration."""
        # Detect Octopus Energy entities
        self._octopus_detected = detect_octopus_energy(self.hass)

        if not self._octopus_detected["has_octopus_energy"]:
            # Skip this step if Octopus Energy is not detected
            self._octopus_enabled = False
            return await self.async_step_rooms()

        if user_input is not None:
            self._octopus_enabled = user_input.get(CONF_OCTOPUS_ENABLED, True)

            if self._octopus_enabled:
                self._octopus_rate_sensor = user_input.get(CONF_OCTOPUS_RATE_SENSOR)
                self._octopus_saving_sensor = user_input.get(CONF_OCTOPUS_SAVING_SENSOR)
            else:
                self._octopus_rate_sensor = None
                self._octopus_saving_sensor = None

            return await self.async_step_rooms()

        # Build schema with detected entities
        rate_sensors = self._octopus_detected.get("rate_sensors", [])
        saving_sensors = self._octopus_detected.get("saving_session_sensors", [])

        schema_fields: dict[Any, Any] = {
            vol.Optional(CONF_OCTOPUS_ENABLED, default=True): bool,
        }

        if rate_sensors:
            schema_fields[
                vol.Optional(
                    CONF_OCTOPUS_RATE_SENSOR,
                    default=rate_sensors[0] if rate_sensors else None,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="monetary",
                    multiple=False,
                )
            )

        if saving_sensors:
            schema_fields[
                vol.Optional(
                    CONF_OCTOPUS_SAVING_SENSOR,
                    default=saving_sensors[0] if saving_sensors else None,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    device_class="plug",
                    multiple=False,
                )
            )

        return self.async_show_form(
            step_id="octopus",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "rate_sensor_count": str(len(rate_sensors)),
                "saving_sensor_count": str(len(saving_sensors)),
            },
        )

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Configure rooms."""
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
                # Start schedule configuration for first room
                self._current_room_idx = 0
                return await self.async_step_schedule()

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

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Configure schedule for each room."""
        if self._current_room_idx >= len(self._rooms):
            return self._create_entry()

        room = self._rooms[self._current_room_idx]
        room_name = room["name"]

        if user_input is not None:
            # Store schedule config
            schedule = {
                CONF_DEFAULT_TEMP: user_input.get(CONF_DEFAULT_TEMP, DEFAULT_TARGET_TEMP),
                CONF_DAY_TEMP: user_input.get(CONF_DAY_TEMP, DEFAULT_DAY_TEMP),
                CONF_NIGHT_TEMP: user_input.get(CONF_NIGHT_TEMP, DEFAULT_NIGHT_TEMP),
                CONF_DAY_START: user_input.get(CONF_DAY_START, DEFAULT_DAY_START),
                CONF_DAY_END: user_input.get(CONF_DAY_END, DEFAULT_DAY_END),
                CONF_USE_WEEKEND_SCHEDULE: user_input.get(CONF_USE_WEEKEND_SCHEDULE, False),
            }

            if schedule[CONF_USE_WEEKEND_SCHEDULE]:
                schedule[CONF_WEEKEND_DAY_TEMP] = user_input.get(
                    CONF_WEEKEND_DAY_TEMP, DEFAULT_DAY_TEMP
                )
                schedule[CONF_WEEKEND_NIGHT_TEMP] = user_input.get(
                    CONF_WEEKEND_NIGHT_TEMP, DEFAULT_NIGHT_TEMP
                )
                schedule[CONF_WEEKEND_DAY_START] = user_input.get(
                    CONF_WEEKEND_DAY_START, DEFAULT_DAY_START
                )
                schedule[CONF_WEEKEND_DAY_END] = user_input.get(
                    CONF_WEEKEND_DAY_END, DEFAULT_DAY_END
                )

            self._rooms[self._current_room_idx][CONF_SCHEDULE] = schedule

            # Move to next room
            self._current_room_idx += 1
            return await self.async_step_schedule()

        return self.async_show_form(
            step_id="schedule",
            data_schema=self._schedule_schema(room_name),
            description_placeholders={"room_name": room_name},
        )

    def _schedule_schema(self, room_name: str) -> vol.Schema:
        """Return the schedule configuration schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_DEFAULT_TEMP, default=DEFAULT_TARGET_TEMP
                ): vol.All(float, vol.Range(min=5.0, max=30.0)),
                vol.Optional(
                    CONF_DAY_TEMP, default=DEFAULT_DAY_TEMP
                ): vol.All(float, vol.Range(min=5.0, max=30.0)),
                vol.Optional(
                    CONF_NIGHT_TEMP, default=DEFAULT_NIGHT_TEMP
                ): vol.All(float, vol.Range(min=5.0, max=30.0)),
                vol.Optional(CONF_DAY_START, default=DEFAULT_DAY_START): str,
                vol.Optional(CONF_DAY_END, default=DEFAULT_DAY_END): str,
                vol.Optional(CONF_USE_WEEKEND_SCHEDULE, default=False): bool,
                vol.Optional(
                    CONF_WEEKEND_DAY_TEMP, default=DEFAULT_DAY_TEMP
                ): vol.All(float, vol.Range(min=5.0, max=30.0)),
                vol.Optional(
                    CONF_WEEKEND_NIGHT_TEMP, default=DEFAULT_NIGHT_TEMP
                ): vol.All(float, vol.Range(min=5.0, max=30.0)),
                vol.Optional(CONF_WEEKEND_DAY_START, default=DEFAULT_DAY_START): str,
                vol.Optional(CONF_WEEKEND_DAY_END, default=DEFAULT_DAY_END): str,
            }
        )

    def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        data: dict[str, Any] = {
            "climate_entities": self._climate_entities,
            CONF_ROOMS: self._rooms,
        }

        # Add Octopus Energy config if enabled
        if self._octopus_enabled:
            data[CONF_OCTOPUS_ENABLED] = True
            if self._octopus_rate_sensor:
                data[CONF_OCTOPUS_RATE_SENSOR] = self._octopus_rate_sensor
            if self._octopus_saving_sensor:
                data[CONF_OCTOPUS_SAVING_SENSOR] = self._octopus_saving_sensor
        else:
            data[CONF_OCTOPUS_ENABLED] = False

        return self.async_create_entry(
            title="Schedy Heating",
            data=data,
        )
