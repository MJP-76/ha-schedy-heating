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

from .const import (
    CONF_CLIMATE_ENTITIES,
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_DAY_TEMP,
    CONF_DEFAULT_TEMP,
    CONF_NIGHT_TEMP,
    CONF_OVERRIDE_ENTITY,
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

_LOGGER = logging.getLogger(__name__)


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
        override_entity = room.get(CONF_OVERRIDE_ENTITY)
        presence_entity = room.get(CONF_PRESENCE_ENTITY)
        schedule = room.get(CONF_SCHEDULE, {})

        entities.append(
            SchedyClimate(
                hass=hass,
                room_name=room_name,
                climate_entity_ids=climate_entity_ids,
                rescheduling_delay=rescheduling_delay,
                override_entity_id=override_entity,
                presence_entity_id=presence_entity,
                schedule=schedule,
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
        override_entity_id: str | None = None,
        presence_entity_id: str | None = None,
        schedule: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the climate entity."""
        self._hass = hass
        self._room_name = room_name
        self._climate_entity_ids = climate_entity_ids
        self._rescheduling_delay = timedelta(minutes=rescheduling_delay)
        self._override_entity_id = override_entity_id
        self._presence_entity_id = presence_entity_id
        self._schedule = schedule or {}
        self._attr_name = f"{room_name} Heating"
        self._attr_unique_id = f"{DOMAIN}_{room_name}_climate"

        # State tracking
        self._scheduled_temp: float = DEFAULT_TARGET_TEMP
        self._manual_override: bool = False
        self._manual_override_until: datetime | None = None
        self._last_manual_temp: float | None = None

        # Entity state references
        self._heating_mode: str = "Home"
        self._heating_season: str = "Summer"
        self._octopus_price: str = "Normal"
        self._heating_bedtime: str = "off"
        self._heating_guests: str = "off"
        self._power_saving: str = "off"
        self._mandj_location: str = "home"
        self._bsp_location: str = "home"
        self._override_state: str = "off"
        self._door_status: str = "off"

    async def async_added_to_hass(self) -> None:
        """Register state listeners and perform initial evaluation."""
        entities_to_watch = [
            "input_select.heating_mode",
            "input_select.heating_season",
            "input_select.octopus_price",
            "input_boolean.heating_bedtime",
            "input_boolean.heating_guests",
            "input_boolean.power_saving",
            "binary_sensor.heating_door_status",
            "person.matthew",
            "person.jenny",
            "person.berrit",
        ]

        # Add room-specific override entity
        if self._override_entity_id:
            entities_to_watch.append(self._override_entity_id)
            # Initialize override state
            state = self._hass.states.get(self._override_entity_id)
            if state:
                self._override_state = state.state

        # Add room-specific presence entity (for bedroom4/berrit)
        if self._presence_entity_id:
            entities_to_watch.append(self._presence_entity_id)

        # Watch underlying climate entities
        for entity_id in self._climate_entity_ids:
            entities_to_watch.append(entity_id)

        async_track_state_change_event(
            self._hass,
            entities_to_watch,
            self._async_handle_state_change,
        )

        # Initialize cached states
        self._async_init_states()

        # Perform initial evaluation
        await self._async_evaluate_schedule()

    @callback
    def _async_init_states(self) -> None:
        """Initialize cached state values from current HA states."""
        state_map = {
            "input_select.heating_mode": "_heating_mode",
            "input_select.heating_season": "_heating_season",
            "input_select.octopus_price": "_octopus_price",
            "input_boolean.heating_bedtime": "_heating_bedtime",
            "input_boolean.heating_guests": "_heating_guests",
            "input_boolean.power_saving": "_power_saving",
            "binary_sensor.heating_door_status": "_door_status",
        }
        for entity_id, attr in state_map.items():
            state = self._hass.states.get(entity_id)
            if state:
                setattr(self, attr, state.state)

        # Initialize presence
        self._async_update_presence_sync()

        # Initialize room-specific presence
        if self._presence_entity_id:
            state = self._hass.states.get(self._presence_entity_id)
            if state:
                self._bsp_location = state.state

    @callback
    def _async_update_presence_sync(self) -> None:
        """Update presence state synchronously."""
        matthew = self._hass.states.get("person.matthew")
        jenny = self._hass.states.get("person.jenny")

        if matthew and jenny:
            if matthew.state == "home" or jenny.state == "home":
                self._mandj_location = "home"
            else:
                self._mandj_location = "not_home"

    @callback
    async def _async_handle_state_change(self, event: Any) -> None:
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
        elif entity_id == self._override_entity_id:
            self._override_state = new_state.state
        elif entity_id == self._presence_entity_id:
            self._bsp_location = new_state.state
        elif entity_id.startswith("person."):
            self._async_update_presence_sync()

        # Re-evaluate the schedule
        await self._async_evaluate_schedule()

    async def _async_evaluate_schedule(self) -> None:
        """Evaluate the schedule and apply the target temperature."""
        now = datetime.now()

        # Check if manual override is still active
        if self._manual_override and self._manual_override_until:
            if now < self._manual_override_until:
                return
            else:
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

        # Rule 3: Presence check
        # If room has specific presence entity (e.g., bedroom4/berrit), use it
        # Otherwise use mandj_location (matthew + jenny)
        if self._presence_entity_id:
            if self._bsp_location == "not_home":
                return 18.0
        else:
            if self._mandj_location == "not_home":
                return 18.0

        # Rule 4: Doors open
        if self._door_status == "on":
            return 17.0

        # Rule 5: Summer
        if self._heating_season == "Summer":
            return 17.0

        # Rule 6: Bedtime
        if self._heating_bedtime == "on":
            return 18.0

        # Rule 7: Early Bedtime mode
        if self._heating_mode == "Early Bedtime":
            return 18.0

        # Rule 8: Holiday
        if self._heating_mode == "Holiday":
            return 17.0

        # Rule 9: Away
        if self._heating_mode == "Away":
            return 17.0

        # Rule 10: Peak pricing
        if self._octopus_price == "Peak":
            return 18.0

        # Rule 11: Christmas
        if self._heating_mode == "Christmas":
            now = datetime.now()
            if 8 <= now.hour < 22:
                return 22.0
            return 18.0

        # Rule 12: Home mode - time-based schedule
        if self._heating_mode == "Home":
            return self._evaluate_time_schedule()

        # Rule 13: OffWork mode
        if self._heating_mode == "OffWork":
            return 18.0

        # Fallback
        return 18.0

    def _evaluate_time_schedule(self) -> float:
        """Evaluate time-based schedule for Home mode."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        current_time = f"{hour:02d}:{minute:02d}"
        is_weekend = now.weekday() >= 5

        # Get schedule config
        use_weekend = self._schedule.get(CONF_USE_WEEKEND_SCHEDULE, False)

        if is_weekend and use_weekend:
            # Weekend schedule
            day_temp = self._schedule.get(CONF_WEEKEND_DAY_TEMP, DEFAULT_DAY_TEMP)
            night_temp = self._schedule.get(CONF_WEEKEND_NIGHT_TEMP, DEFAULT_NIGHT_TEMP)
            day_start = self._schedule.get(CONF_WEEKEND_DAY_START, DEFAULT_DAY_START)
            day_end = self._schedule.get(CONF_WEEKEND_DAY_END, DEFAULT_DAY_END)
        else:
            # Weekday schedule
            day_temp = self._schedule.get(CONF_DAY_TEMP, DEFAULT_DAY_TEMP)
            night_temp = self._schedule.get(CONF_NIGHT_TEMP, DEFAULT_NIGHT_TEMP)
            day_start = self._schedule.get(CONF_DAY_START, DEFAULT_DAY_START)
            day_end = self._schedule.get(CONF_DAY_END, DEFAULT_DAY_END)

        # Check if current time is within day hours
        if day_start <= current_time < day_end:
            return day_temp
        return night_temp

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

            await self._hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": entity_id,
                    "temperature": self._attr_target_temperature,
                },
                blocking=True,
            )

            if self._attr_hvac_mode == HVACMode.OFF:
                await self._hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": entity_id, "hvac_mode": HVACMode.OFF},
                    blocking=True,
                )
            elif state.state == HVACMode.OFF and self._attr_hvac_mode == HVACMode.HEAT:
                await self._hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
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
            "bsp_location": self._bsp_location if self._presence_entity_id else None,
            "door_status": self._door_status,
            "override_entity": self._override_entity_id,
            "presence_entity": self._presence_entity_id,
            "underlying_entities": self._climate_entity_ids,
            "schedule": self._schedule,
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
