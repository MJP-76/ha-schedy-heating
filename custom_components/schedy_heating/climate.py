"""Climate entities for Schedy Heating."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_CLIMATE_ENTITIES,
    CONF_RESCHEDULING_DELAY,
    CONF_ROOMS,
    CONF_ROOM_NAME,
    DEFAULT_RESCHEDULING_DELAY,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Default schedule rules matching the Schedy config
DEFAULT_SCHEDULE_RULES = [
    {"condition": "octopus_price == 'Plunge'", "temp": 21.0},
    {"condition": "override == 'on'", "temp": 20.0},
    {"condition": "mandj_location == 'not_home'", "temp": 18.0},
    {"condition": "heating_season == 'Summer'", "temp": 17.0},
    {"condition": "heating_bedtime == 'on'", "temp": 18.0},
    {"condition": "heating_mode == 'Early Bedtime'", "temp": 18.0},
    {"condition": "heating_mode == 'Holiday'", "temp": 17.0},
    {"condition": "heating_mode == 'Away'", "temp": 17.0},
    {"condition": "octopus_price == 'Peak'", "temp": 18.0},
    {"condition": "heating_mode == 'Christmas'", "temp": 22.0},
    {"condition": "heating_mode == 'Home'", "temp": 19.0},
    {"condition": "heating_mode == 'OffWork'", "temp": 18.0},
    {"condition": "default", "temp": 18.0},
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities for Schedy Heating."""
    rooms = entry.data.get(CONF_ROOMS, [])
    entities = []

    for room in rooms:
        room_name = room[CONF_ROOM_NAME]
        climate_entity_ids = room.get(CONF_CLIMATE_ENTITIES, [])
        rescheduling_delay = room.get(
            CONF_RESCHEDULING_DELAY, DEFAULT_RESCHEDULING_DELAY
        )

        entities.append(
            SchedyClimate(
                hass=hass,
                room_name=room_name,
                climate_entity_ids=climate_entity_ids,
                rescheduling_delay=rescheduling_delay,
            )
        )

    async_add_entities(entities)


class SchedyClimate(ClimateEntity):
    """Climate entity that wraps real thermostats with schedule logic."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature = DEFAULT_TARGET_TEMP
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(
        self,
        hass: HomeAssistant,
        room_name: str,
        climate_entity_ids: list[str],
        rescheduling_delay: int,
    ) -> None:
        """Initialize the climate entity."""
        self._hass = hass
        self._room_name = room_name
        self._climate_entity_ids = climate_entity_ids
        self._rescheduling_delay = timedelta(minutes=rescheduling_delay)
        self._attr_name = f"{room_name} Heating"
        self._attr_unique_id = f"{DOMAIN}_{room_name}_climate"

        # State tracking
        self._scheduled_temp: float = DEFAULT_TARGET_TEMP
        self._manual_override: bool = False
        self._manual_override_until: datetime | None = None
        self._last_manual_temp: float | None = None
        self._current_target: float = DEFAULT_TARGET_TEMP

        # Entity state references
        self._heating_mode: str = "Home"
        self._heating_season: str = "Summer"
        self._octopus_price: str = "Normal"
        self._heating_bedtime: str = "off"
        self._heating_guests: str = "off"
        self._power_saving: str = "off"
        self._mandj_location: str = "home"
        self._override_state: str = "off"
        self._door_status: str = "off"

    async def async_added_to_hass(self) -> None:
        """Register state listeners and perform initial evaluation."""
        # Listen for changes to entities that affect the schedule
        entities_to_watch = [
            "input_select.heating_mode",
            "input_select.heating_season",
            "input_select.octopus_price",
            "input_boolean.heating_bedtime",
            "input_boolean.heating_guests",
            "input_boolean.power_saving",
            "binary_sensor.heating_door_status",
        ]

        # Add person trackers
        entities_to_watch.extend(
            [
                "person.matthew",
                "person.jenny",
                "person.berrit",
            ]
        )

        # Add override entities for this room
        for entity_id in self._climate_entity_ids:
            # Watch the underlying climate entities
            entities_to_watch.append(entity_id)

        # Register state change listeners
        async_track_state_change_event(
            self._hass,
            entities_to_watch,
            self._async_handle_state_change,
        )

        # Perform initial evaluation
        await self._async_evaluate_schedule()

    @callback
    async def _async_handle_state_change(
        self, event: Any
    ) -> None:
        """Handle state changes of watched entities."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if new_state is None:
            return

        # Update cached state values
        if entity_id == "input_select.heating_mode":
            self._heating_mode = new_state.state
        elif entity_id == "input_select.heating_season":
            self._heating_season = new_state.state
        elif entity_id == "input_select.octopus_price":
            self._octopus_price = new_state.state
        elif entity_id == "input_boolean.heating_bedtime":
            self._heating_bedtime = new_state.state
        elif entity_id == "input_boolean.heating_guests":
            self._heating_guests = new_state.state
        elif entity_id == "input_boolean.power_saving":
            self._power_saving = new_state.state
        elif entity_id == "binary_sensor.heating_door_status":
            self._door_status = new_state.state
        elif entity_id.startswith("person."):
            await self._async_update_presence()
            return

        # Re-evaluate the schedule
        await self._async_evaluate_schedule()

    async def _async_update_presence(self) -> None:
        """Update presence state from person entities."""
        matthew = self._hass.states.get("person.matthew")
        jenny = self._hass.states.get("person.jenny")

        if matthew and jenny:
            if matthew.state == "home" or jenny.state == "home":
                self._mandj_location = "home"
            else:
                self._mandj_location = "not_home"

        await self._async_evaluate_schedule()

    async def _async_evaluate_schedule(self) -> None:
        """Evaluate the schedule and apply the target temperature."""
        now = datetime.now()

        # Check if manual override is still active
        if self._manual_override and self._manual_override_until:
            if now < self._manual_override_until:
                # Manual override still active, don't change
                return
            else:
                # Manual override expired
                self._manual_override = False
                self._manual_override_until = None

        # Evaluate rules in priority order
        new_temp = self._evaluate_rules()

        if new_temp != self._scheduled_temp:
            self._scheduled_temp = new_temp
            self._attr_target_temperature = new_temp
            self.async_write_ha_state()
            await self._async_apply_to_underlying()

    def _evaluate_rules(self) -> float:
        """Evaluate schedule rules and return the target temperature."""
        # Rule 1: Plunge pricing
        if self._octopus_price == "Plunge":
            return 21.0

        # Rule 2: Room override
        if self._override_state == "on":
            return 20.0

        # Rule 3: Everyone away
        if self._mandj_location == "not_home":
            return 18.0

        # Rule 4: Summer
        if self._heating_season == "Summer":
            return 17.0

        # Rule 5: Bedtime
        if self._heating_bedtime == "on":
            return 18.0

        # Rule 6: Early Bedtime mode
        if self._heating_mode == "Early Bedtime":
            return 18.0

        # Rule 7: Holiday
        if self._heating_mode == "Holiday":
            return 17.0

        # Rule 8: Away
        if self._heating_mode == "Away":
            return 17.0

        # Rule 9: Peak pricing
        if self._octopus_price == "Peak":
            return 18.0

        # Rule 10: Christmas
        if self._heating_mode == "Christmas":
            now = datetime.now()
            if 8 <= now.hour < 22:
                return 22.0
            return 18.0

        # Rule 11: Home mode - time-based schedule
        if self._heating_mode == "Home":
            return self._evaluate_time_schedule()

        # Rule 12: OffWork mode
        if self._heating_mode == "OffWork":
            return 18.0

        # Fallback
        return 18.0

    def _evaluate_time_schedule(self) -> float:
        """Evaluate time-based schedule for Home mode."""
        now = datetime.now()
        hour = now.hour
        is_weekend = now.weekday() >= 5  # Saturday=5, Sunday=6

        # Simple time-based schedule
        if is_weekend:
            # Weekend schedule
            if 8 <= hour < 21:
                return 21.0
            else:
                return 19.0
        else:
            # Weekday schedule
            if 15 <= hour < 21:
                return 21.0
            else:
                return 19.0

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature (manual override)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        self._manual_override = True
        self._manual_override_until = datetime.now() + self._rescheduling_delay
        self._last_manual_temp = temp
        self._attr_target_temperature = temp
        self.async_write_ha_state()

        await self._async_apply_to_underlying()

        _LOGGER.info(
            "Manual override for %s: %.1f°C (expires in %s)",
            self._room_name,
            temp,
            self._rescheduling_delay,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

        await self._async_apply_to_underlying()

    async def _async_apply_to_underlying(self) -> None:
        """Apply target temperature to underlying climate entities."""
        for entity_id in self._climate_entity_ids:
            state = self._hass.states.get(entity_id)
            if state is None:
                _LOGGER.warning("Underlying entity %s not found", entity_id)
                continue

            # Set temperature on the underlying entity
            await self._hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": entity_id,
                    "temperature": self._attr_target_temperature,
                },
                blocking=True,
            )

            # Set HVAC mode if needed
            if self._attr_hvac_mode == HVACMode.OFF:
                await self._hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {
                        "entity_id": entity_id,
                        "hvac_mode": HVACMode.OFF,
                    },
                    blocking=True,
                )
            elif state.state == HVACMode.OFF and self._attr_hvac_mode == HVACMode.HEAT:
                await self._hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {
                        "entity_id": entity_id,
                        "hvac_mode": HVACMode.HEAT,
                    },
                    blocking=True,
                )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "scheduled_temperature": self._scheduled_temp,
            "manual_override": self._manual_override,
            "manual_override_until": self._manual_override_until.isoformat()
            if self._manual_override_until
            else None,
            "heating_mode": self._heating_mode,
            "heating_season": self._heating_season,
            "octopus_price": self._octopus_price,
            "mandj_location": self._mandj_location,
            "underlying_entities": self._climate_entity_ids,
        }

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature from the first underlying entity."""
        for entity_id in self._climate_entity_ids:
            state = self._hass.states.get(entity_id)
            if state and state.attributes.get("current_temperature"):
                return float(state.attributes["current_temperature"])
        return None
