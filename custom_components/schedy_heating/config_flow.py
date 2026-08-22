"""Config flow for Schedy Heating integration."""

from __future__ import annotations

import logging
import os
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

# Paths where Schedy AppDaemon config might be found
SCHEDY_CONFIG_PATHS = [
    "/addon_configs/a0d7b954_appdaemon/apps/hassapps-heating.yaml",
    "/config/appdaemon/apps/hassapps-heating.yaml",
    "/homeassistant/appdaemon/apps/hassapps-heating.yaml",
    "/config/hassapps-heating.yaml",
]


def _detect_schedy_installed(hass: HomeAssistant) -> bool:
    """Detect if Schedy AppDaemon app is installed and configured.

    Checks for:
    1. hassapps-heating.yaml config file
    2. Schedy-managed climate entities
    """
    # Check for config file
    for path in SCHEDY_CONFIG_PATHS:
        if os.path.exists(path):
            _LOGGER.info("Found Schedy config at %s", path)
            return True

    # Check for Schedy-managed entities (heating_mode, heating_season, etc.)
    schedy_entities = [
        "input_select.heating_mode",
        "input_select.heating_season",
        "binary_sensor.heating_door_status",
    ]
    for entity_id in schedy_entities:
        if hass.states.get(entity_id) is not None:
            _LOGGER.info("Found Schedy entity: %s", entity_id)
            return True

    return False


def _get_schedy_config(hass: HomeAssistant) -> dict[str, Any] | None:
    """Read existing Schedy configuration if available.

    Returns:
        Dict with parsed Schedy config or None if not found.
    """
    import yaml

    for path in SCHEDY_CONFIG_PATHS:
        try:
            if os.path.exists(path):
                with open(path) as f:
                    config = yaml.safe_load(f)

                if config and "tock_heating" in config:
                    _LOGGER.info("Read Schedy config from %s", path)
                    return config["tock_heating"]
        except Exception as e:
            _LOGGER.warning("Failed to read Schedy config from %s: %s", path, e)

    # Try to find config by searching common locations
    search_paths = [
        "/addon_configs",
        "/config",
        "/homeassistant",
    ]

    for base_path in search_paths:
        try:
            if os.path.exists(base_path):
                for root, dirs, files in os.walk(base_path):
                    if "hassapps-heating.yaml" in files:
                        config_path = os.path.join(root, "hassapps-heating.yaml")
                        _LOGGER.info("Found Schedy config at %s", config_path)
                        with open(config_path) as f:
                            config = yaml.safe_load(f)
                        if config and "tock_heating" in config:
                            return config["tock_heating"]
        except Exception as e:
            _LOGGER.warning("Error searching %s: %s", base_path, e)

    return None


def _get_schedy_climate_entities(schedy_config: dict[str, Any]) -> list[str]:
    """Extract climate entity IDs from Schedy config.

    Returns:
        List of climate entity IDs found in the Schedy rooms config.
    """
    entities = []
    rooms = schedy_config.get("rooms", {})

    for room_name, room_config in rooms.items():
        actors = room_config.get("actors", {})
        for entity_id in actors:
            if entity_id.startswith("climate."):
                entities.append(entity_id)

    return entities


def _get_schedy_rooms(schedy_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract room configurations from Schedy config.

    Returns:
        List of room dicts with name and climate entities.
    """
    rooms = []
    schedy_rooms = schedy_config.get("rooms", {})

    for room_name, room_config in schedy_rooms.items():
        actors = room_config.get("actors", {})
        climate_entities = [
            eid for eid in actors if eid.startswith("climate.")
        ]

        if climate_entities:
            rooms.append(
                {
                    "name": room_name.replace("_", " ").title(),
                    "climate_entities": climate_entities,
                    "rescheduling_delay": room_config.get(
                        "rescheduling_delay", 60
                    ),
                }
            )

    return rooms


def _read_schedy_config_from_path(config_path: str) -> dict[str, Any] | None:
    """Read Schedy config from a user-provided path.

    Args:
        config_path: Path to the hassapps-heating.yaml file

    Returns:
        Dict with parsed Schedy config or None if not found.
    """
    import yaml

    try:
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = yaml.safe_load(f)

            if config and "tock_heating" in config:
                _LOGGER.info("Read Schedy config from user-provided path: %s", config_path)
                return config["tock_heating"]
            else:
                _LOGGER.warning("Config file found but no 'tock_heating' key: %s", config_path)
        else:
            _LOGGER.warning("Config file not found at: %s", config_path)
    except Exception as e:
        _LOGGER.warning("Failed to read Schedy config from %s: %s", config_path, e)

    return None


def _parse_schedy_config_yaml(config_yaml: str) -> dict[str, Any] | None:
    """Parse Schedy config from a YAML string.

    Args:
        config_yaml: YAML string content of hassapps-heating.yaml

    Returns:
        Dict with parsed Schedy config or None if parsing fails.
    """
    import yaml

    try:
        config = yaml.safe_load(config_yaml)

        if config and "tock_heating" in config:
            _LOGGER.info("Parsed Schedy config from pasted YAML")
            return config["tock_heating"]
        else:
            _LOGGER.warning("Pasted YAML does not contain 'tock_heating' key")
    except Exception as e:
        _LOGGER.warning("Failed to parse pasted YAML: %s", e)

    return None


def _get_all_climate_entities(hass: HomeAssistant) -> list[dict[str, str]]:
    """Get all climate entities formatted for selector."""
    entities = []
    for state in hass.states.async_all("climate"):
        entities.append(
            {
                "value": state.entity_id,
                "label": state.attributes.get("friendly_name", state.entity_id),
            }
        )
    return entities


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
        self._schedy_config: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Check prerequisites and select climate entities."""
        # Check if Schedy is installed
        schedy_installed = _detect_schedy_installed(self.hass)

        if not schedy_installed:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors={"base": "schedy_not_found"},
                description_placeholders={
                    "error": "Schedy AppDaemon app not found. Please install and configure Schedy first."
                },
            )

        # Try to read existing Schedy config
        self._schedy_config = _get_schedy_config(self.hass)

        # If config not found, ask user to paste it
        if not self._schedy_config:
            if user_input is not None:
                # Check if user pasted config or provided path
                config_input = user_input.get("config_yaml", "")

                if config_input:
                    # Check if it's a file path or YAML content
                    if config_input.strip().startswith("/") or config_input.strip().endswith(".yaml"):
                        # It's a file path
                        self._schedy_config = _read_schedy_config_from_path(config_input.strip())
                    else:
                        # It's YAML content
                        self._schedy_config = _parse_schedy_config_yaml(config_input)

                # Get selected entities
                self._climate_entities = user_input.get(CONF_CLIMATE_ENTITIES, [])
                if self._climate_entities:
                    return await self.async_step_octopus()

                # If config was found, re-show form with pre-selected entities
                if self._schedy_config:
                    default_entities = _get_schedy_climate_entities(self._schedy_config)
                    climate_entities = _get_all_climate_entities(self.hass)
                    return self.async_show_form(
                        step_id="user",
                        data_schema=vol.Schema(
                            {
                                vol.Required(
                                    CONF_CLIMATE_ENTITIES,
                                    default=default_entities,
                                ): selector.SelectSelector(
                                    selector.SelectSelectorConfig(
                                        options=climate_entities,
                                        multiple=True,
                                        mode=selector.SelectSelectorMode.LIST,
                                    )
                                ),
                            }
                        ),
                        description_placeholders={
                            "schedy_config": f"Found {len(default_entities)} entities in Schedy config"
                        },
                    )

            # Get all available climate entities
            climate_entities = _get_all_climate_entities(self.hass)

            if not climate_entities:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({}),
                    errors={"base": "no_climate_entities"},
                )

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Optional("config_yaml"): str,
                        vol.Required(CONF_CLIMATE_ENTITIES, default=[]): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=climate_entities,
                                multiple=True,
                                mode=selector.SelectSelectorMode.LIST,
                            )
                        ),
                    }
                ),
                description_placeholders={
                    "schedy_config": "Could not read Schedy config automatically. Paste your hassapps-heating.yaml content below, or select entities manually."
                },
            )

        if user_input is not None:
            self._climate_entities = user_input[CONF_CLIMATE_ENTITIES]
            return await self.async_step_octopus()

        # Get all available climate entities
        climate_entities = _get_all_climate_entities(self.hass)

        if not climate_entities:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors={"base": "no_climate_entities"},
            )

        # Pre-select entities from Schedy config if available
        default_entities = []
        if self._schedy_config:
            default_entities = _get_schedy_climate_entities(self._schedy_config)
            _LOGGER.info(
                "Pre-selecting %d entities from Schedy config: %s",
                len(default_entities),
                default_entities,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CLIMATE_ENTITIES,
                        default=default_entities,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=climate_entities,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            description_placeholders={
                "schedy_config": f"Found {len(default_entities)} entities in Schedy config"
                if default_entities
                else "No existing config found"
            },
        )

    async def async_step_octopus(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Configure Octopus Energy integration."""
        self._octopus_detected = detect_octopus_energy(self.hass)

        if not self._octopus_detected["has_octopus_energy"]:
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

        rate_sensors = self._octopus_detected.get("rate_sensors", [])
        saving_sensors = self._octopus_detected.get("saving_session_sensors", [])

        schema_fields: dict[Any, Any] = {
            vol.Optional(CONF_OCTOPUS_ENABLED, default=True): bool,
        }

        if rate_sensors:
            rate_options = [
                {"value": s, "label": s.split(".")[-1].replace("_", " ").title()}
                for s in rate_sensors
            ]
            schema_fields[
                vol.Optional(
                    CONF_OCTOPUS_RATE_SENSOR,
                    default=rate_sensors[0],
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=rate_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        if saving_sensors:
            saving_options = [
                {"value": s, "label": s.split(".")[-1].replace("_", " ").title()}
                for s in saving_sensors
            ]
            schema_fields[
                vol.Optional(
                    CONF_OCTOPUS_SAVING_SENSOR,
                    default=saving_sensors[0],
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=saving_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
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
        # Pre-populate rooms from Schedy config if available
        if not self._rooms and self._schedy_config:
            schedy_rooms = _get_schedy_rooms(self._schedy_config)
            # Only include rooms that have climate entities we selected
            for room in schedy_rooms:
                selected_entities = [
                    e for e in room["climate_entities"]
                    if e in self._climate_entities
                ]
                if selected_entities:
                    room["climate_entities"] = selected_entities
                    self._rooms.append(room)
                    _LOGGER.info(
                        "Imported room '%s' with entities: %s",
                        room["name"],
                        selected_entities,
                    )

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
        climate_entities = _get_all_climate_entities(self.hass)
        climate_options = [
            {"value": e["value"], "label": e["label"]} for e in climate_entities
        ]

        # Get all input_boolean entities for overrides
        override_options = [
            {
                "value": state.entity_id,
                "label": state.attributes.get("friendly_name", state.entity_id),
            }
            for state in self.hass.states.async_all("input_boolean")
            if "hvac" in state.entity_id.lower() or "override" in state.entity_id.lower()
        ]

        # Get all person entities for presence
        presence_options = [
            {
                "value": state.entity_id,
                "label": state.attributes.get("friendly_name", state.entity_id),
            }
            for state in self.hass.states.async_all("person")
        ]

        schema_fields: dict[Any, Any] = {
            vol.Optional("room_name"): str,
            vol.Optional("room_climate_entities", default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=climate_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                "rescheduling_delay", default=DEFAULT_RESCHEDULING_DELAY
            ): vol.All(int, vol.Range(min=0, max=1440)),
        }

        if override_options:
            schema_fields[
                vol.Optional("override_entity")
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=override_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        if presence_options:
            schema_fields[
                vol.Optional("presence_entity")
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=presence_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        schema_fields[vol.Optional("add_another", default=False)] = bool
        schema_fields[vol.Optional("finish", default=True)] = bool

        return vol.Schema(schema_fields)

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Configure schedule for each room."""
        if self._current_room_idx >= len(self._rooms):
            return self._create_entry()

        room = self._rooms[self._current_room_idx]
        room_name = room["name"]

        if user_input is not None:
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

        if self._octopus_enabled:
            data[CONF_OCTOPUS_ENABLED] = True
            if self._octopus_rate_sensor:
                data[CONF_OCTOPUS_RATE_SENSOR] = self._octopus_rate_sensor
            if self._octopus_saving_sensor:
                data[CONF_OCTOPUS_SAVING_SENSOR] = self._octopus_saving_sensor
        else:
            data[CONF_OCTOPUS_ENABLED] = False

        return self.async_create_entry(
            title="Schedy Heating UI",
            data=data,
        )
