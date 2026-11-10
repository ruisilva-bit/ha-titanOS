"""Production options; controls work without experimental validation switches."""

from ipaddress import IPv4Address
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlow

from .settings import DEFAULT_OPTIONS, option_enabled


class TitanOSOptionsFlow(OptionsFlow):
    """Configure normal controls and optional firmware-specific features."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Store preferences without changing the existing pairing credentials."""
        errors = {}
        if user_input is not None:
            try:
                IPv4Address(user_input.get("broadcast", "255.255.255.255"))
            except ValueError:
                errors["base"] = "invalid_broadcast"
            else:
                return self.async_create_entry(title="", data=user_input)
        defaults = self.config_entry.options
        schema: dict[Any, Any] = {
            vol.Optional(key, default=option_enabled(defaults, key)): bool
            for key in DEFAULT_OPTIONS
        }
        schema[
            vol.Optional(
                "broadcast", default=defaults.get("broadcast", "255.255.255.255")
            )
        ] = str
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
