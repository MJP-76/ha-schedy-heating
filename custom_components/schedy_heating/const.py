"""Constants for the Schedy Heating integration."""

DOMAIN = "schedy_heating"

# Config flow steps
STEP_USER = "user"
STEP_ROOMS = "rooms"
STEP_SCHEDULE = "schedule"

# Config keys
CONF_ROOMS = "rooms"
CONF_ROOM_NAME = "room_name"
CONF_CLIMATE_ENTITIES = "climate_entities"
CONF_OVERRIDE_ENTITY = "override_entity"
CONF_RESCHEDULING_DELAY = "rescheduling_delay"
CONF_SCHEDULE = "schedule"
CONF_WEEKDAYS = "weekdays"
CONF_RULES = "rules"

# Entity domains
DOMAIN_CLIMATE = "climate"
DOMAIN_INPUT_BOOLEAN = "input_boolean"
DOMAIN_INPUT_SELECT = "input_select"
DOMAIN_PERSON = "person"
DOMAIN_BINARY_SENSOR = "binary_sensor"

# Heating modes
HEATING_MODES = ["Home", "OffWork", "Away", "Holiday", "Early Bedtime", "Christmas"]
DEFAULT_HEATING_MODE = "Home"

# Seasons
SEASONS = ["Winter", "Summer"]
DEFAULT_SEASON = "Summer"

# Octopus price tiers
OCTOPUS_PRICES = ["Normal", "Peak", "Plunge"]
DEFAULT_OCTOPUS_PRICE = "Normal"

# Default values
DEFAULT_RESCHEDULING_DELAY = 60
DEFAULT_TARGET_TEMP = 18.0

# Platforms
PLATFORMS = ["select", "binary_sensor"]
