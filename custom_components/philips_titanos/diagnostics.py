"""Home Assistant diagnostics without config-entry credentials or raw payloads."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import TitanOSConfigEntry
from .settings import DEFAULT_OPTIONS, option_enabled


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TitanOSConfigEntry
) -> dict[str, Any]:
    """Return allowlisted runtime facts, not a dump of entry data."""
    coordinator = entry.runtime_data
    return {
        "protocol": "jointspace_v6_https_digest",
        "connected": coordinator.last_update_success,
        "power_evidence": coordinator.power.state.value,
        "power_trusted": option_enabled(entry.options, "trust_powerstate"),
        "last_success": coordinator.last_success,
        "last_error": coordinator.last_error,
        "consecutive_failures": coordinator.failures,
        "dial_registrations": list(coordinator.dial_apps),
        "unsupported_endpoints": sorted(coordinator.optional_unavailable),
        "standby_unconfirmed": coordinator.power.uncertain_standby_sent,
        "capabilities": {
            key: option_enabled(entry.options, key) for key in DEFAULT_OPTIONS
        },
    }
