"""Sidebar "TV" panel with native buttons bound to this TV's entities.

The panel is registered by the integration through public Home Assistant APIs,
so it appears on its own after the TV is added. It needs no HACS frontend card
and no YAML pasted by hand.
"""

from pathlib import Path
import re

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_COMPONENT = "philips-titanos-remote-panel"
STATIC_URL = "/philips_titanos_panel"
MODULE_NAME = "titanos-remote.js"
FRONTEND_DIR = Path(__file__).parent / "frontend"
_STATIC_DONE = f"{DOMAIN}_static_registered"


def panel_url_path(entry: ConfigEntry) -> str:
    """Return a stable sidebar URL for this TV, derived from its serial."""
    serial = re.sub(r"[^a-z0-9]+", "-", (entry.unique_id or "").lower()).strip("-")
    return f"philips-titanos-{serial or entry.entry_id.lower()}"


async def _async_register_static(hass: HomeAssistant) -> None:
    """Serve the panel module once per Home Assistant run."""
    if hass.data.get(_STATIC_DONE):
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
    )
    hass.data[_STATIC_DONE] = True


async def async_register_panel(
    hass: HomeAssistant,
    entry: ConfigEntry,
    remote_entity_id: str,
    player_entity_id: str,
) -> None:
    """Add the TV panel to the sidebar, bound to the entity IDs of this TV."""
    await _async_register_static(hass)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=panel_url_path(entry),
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=entry.title,
        sidebar_icon="mdi:television",
        module_url=f"{STATIC_URL}/{MODULE_NAME}",
        config={"remote": remote_entity_id, "player": player_entity_id},
        require_admin=False,
    )


def async_unregister_panel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove this TV's panel on unload or reload."""
    frontend.async_remove_panel(hass, panel_url_path(entry), warn_if_unknown=False)
