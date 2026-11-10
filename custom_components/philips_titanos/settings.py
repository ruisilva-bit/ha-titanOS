"""Production settings with backward-compatible optional-feature preferences."""

from collections.abc import Mapping
from typing import Any

DEFAULT_OPTIONS = {
    "enable_controls": True,
    "enable_wol": True,
    "enable_dial": False,
    "enable_ambilight": False,
    "trust_powerstate": False,
    "trust_mute_state": False,
}
LEGACY_OPTIONS = {
    "enable_dial": "dial_verified",
    "enable_ambilight": "ambilight_verified",
    "trust_powerstate": "powerstate_verified",
    "trust_mute_state": "mute_state_verified",
}


def option_enabled(options: Mapping[str, Any], key: str) -> bool:
    """Preserve optional choices, but never carry forward obsolete test locks.

    keys_verified, remote_testing and wol_verified were experimental validation
    gates, not user disable switches. Production controls no longer require them.
    The new enable_controls/enable_wol settings are explicit opt-out switches.
    """
    if key in options:
        return bool(options[key])
    if (legacy := LEGACY_OPTIONS.get(key)) and legacy in options:
        return bool(options[legacy])
    return DEFAULT_OPTIONS[key]
