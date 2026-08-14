# Schedy Heating

Home Assistant integration for Schedy-style heating schedules with visual config flow.

## Features

- **Visual Config Flow** — Set up rooms and assign climate entities through the HA UI
- **Heating Modes** — Home, OffWork, Away, Holiday, Early Bedtime, Christmas
- **Season Support** — Winter/Summer temperature profiles
- **Octopus Energy Integration** — Responds to Plunge/Peak pricing
- **Presence Detection** — Reduces heating when occupants are away
- **Door Sensors** — Drops temperature when doors are open
- **Per-Room Overrides** — Temporary temperature overrides with configurable rescheduling delay
- **Bedtime Mode** — Automatic temperature reduction at bedtime

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add `https://github.com/MJP-76/ha-schedy-heating` as an Integration
5. Install "Schedy Heating"
6. Restart Home Assistant

### Manual

1. Copy the `custom_components/schedy_heating` folder to your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration" and search for "Schedy Heating"
3. Select the climate entities you want to manage
4. Configure rooms and assign climate entities

## Entities Created

### Select Entities
- **Heating Mode** — Home, OffWork, Away, Holiday, Early Bedtime, Christmas
- **Heating Season** — Winter, Summer
- **Octopus Price** — Normal, Peak, Plunge

### Binary Sensors
- **Room Override** — Per-room override toggle (created automatically for each room)

## Schedule Rules

The integration evaluates rules in priority order:

1. **Plunge pricing** — Boost to 21°C
2. **Room override** — Use override temperature
3. **Presence** — Drop to 18°C when all occupants away
4. **Summer** — Drop to 17°C
5. **Bedtime** — Drop to 18°C (20°C for bedrooms)
6. **Early Bedtime** — Override to bedtime temperatures
7. **Peak pricing** — Reduce to 18°C
8. **Holiday/Away** — Drop to 17°C
9. **Christmas** — Boost to 22°C (08:00–22:00)
10. **Time-based snippets** — Apply weekday/weekend schedules
11. **Fallback** — Default 18°C

## Manual Override Protection

When someone manually adjusts a thermostat, the integration waits `rescheduling_delay` minutes (default: 60) before re-applying the schedule. Mode changes bypass this delay and apply immediately.

## Links

- [GitHub Repository](https://github.com/MJP-76/ha-schedy-heating)
- [Issues](https://github.com/MJP-76/ha-schedy-heating/issues)
- [Schedy Documentation](https://hass-apps.readthedocs.io/en/latest/apps/schedy/index.html)
