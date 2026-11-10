"""User-confirmed capabilities; never guess model compatibility."""

from ipaddress import IPv4Address
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlow

CAPABILITIES = (
    "dial_verified",
    "keys_verified",
    "wol_verified",
    "powerstate_verified",
    "mute_state_verified",
    "ambilight_verified",
)


class TitanOSOptionsFlow(OptionsFlow):
    """Enable controls only following observed hardware validation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Store options separately, preserving all existing pairing data."""
        errors = {}
        if user_input is not None:
            try:
                IPv4Address(user_input.get("broadcast", "255.255.255.255"))
            except ValueError:
                errors["base"] = "invalid_broadcast"
            else:
                return self.async_create_entry(title="", data=user_input)
        defaults = self.config_entry.options
        schema = {
            vol.Optional(key, default=defaults.get(key, False)): bool
            for key in CAPABILITIES
        }
        schema[
            vol.Optional(
                "broadcast", default=defaults.get("broadcast", "255.255.255.255")
            )
        ] = str
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
