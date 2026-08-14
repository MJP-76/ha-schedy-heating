# Schedy Heating

A powerful Home Assistant integration for intelligent heating control with schedule-driven climate entities.

## Features

- **Visual Config Flow** — Set up rooms and assign climate entities through the HA UI
- **Heating Modes** — Home, OffWork, Away, Holiday, Early Bedtime, Christmas
- **Season Support** — Winter/Summer temperature profiles
- **Octopus Energy Integration** — Auto-detects Octopus Energy for Plunge/Peak pricing
- **Presence Detection** — Reduces heating when occupants are away
- **Door Sensors** — Drops temperature when doors are open
- **Per-Room Overrides** — Temporary temperature overrides with configurable rescheduling delay
- **Bedtime Mode** — Automatic temperature reduction at bedtime
- **Time-Based Schedules** — Configurable day/night temperatures with weekend support

## How It Works

Schedy Heating wraps your existing climate entities (thermostats) with intelligent schedule logic. It evaluates rules in priority order to determine the optimal target temperature for each room.

### Rule Priority

1. **Plunge pricing** — Boost to 21°C (Octopus Energy)
2. **Room override** — Use override temperature
3. **Presence** — Drop to 18°C when all occupants away
4. **Doors open** — Drop to 17°C
5. **Summer** — Drop to 17°C
6. **Bedtime** — Drop to 18°C (20°C for bedrooms)
7. **Early Bedtime** — Override to bedtime temperatures
8. **Holiday/Away** — Drop to 17°C
9. **Peak pricing** — Reduce to 18°C
10. **Christmas** — Boost to 22°C (08:00–22:00)
11. **Home mode** — Apply time-based schedule
12. **OffWork** — Drop to 18°C
13. **Fallback** — Default 18°C

### Manual Override Protection

When someone manually adjusts a thermostat, the integration waits a configurable delay (default: 60 minutes) before re-applying the schedule. Mode changes bypass this delay and apply immediately.

### Octopus Energy

If you have Octopus Energy installed, the integration will:
- Auto-detect your electricity rate sensor
- Auto-detect saving session sensors
- Automatically switch between Normal/Peak/Plunge pricing
- Drop temperature during saving sessions

## Entities Created

### Select Entities
- **Heating Mode** — Home, OffWork, Away, Holiday, Early Bedtime, Christmas
- **Heating Season** — Winter, Summer
- **Octopus Price** — Normal, Peak, Plunge (manual fallback if Octopus not installed)

### Climate Entities
- **Room Heating** — One per room, wraps underlying thermostats with schedule logic

### Binary Sensors
- **Room Override** — Per-room override toggle (created automatically for each room)

## Support

- [GitHub Issues](https://github.com/MJP-76/ha-schedy-heating/issues)
- [Schedy Documentation](https://hass-apps.readthedocs.io/en/latest/apps/schedy/index.html)
