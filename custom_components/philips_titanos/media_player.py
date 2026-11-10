# Modified by Alex for ha-titanOS; derived from ksooo/ha-philips-titanos.
# Upstream code is Apache-2.0: see LICENSE.upstream and NOTICE.
"""Media player for the Philips Titan OS TV integration."""

from typing import Any, override

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TitanOSConfigEntry, TitanOSCoordinator
from .entity import TitanOSEntity

PARALLEL_UPDATES = 1

SOURCE_HOME = "Home"
SOURCE_LIVE_TV = "Live TV"
SOURCE_HDMI = "HDMI"

_LIVE_TV_FEATURES = (
    MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)

_ACTIVITY_SOURCES = {
    "browser": SOURCE_HOME,
    "watchtv": SOURCE_LIVE_TV,
    "extension": SOURCE_HDMI,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TitanOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player."""
    async_add_entities([TitanOSMediaPlayer(entry.runtime_data)])


class TitanOSMediaPlayer(TitanOSEntity, MediaPlayerEntity):
    """The TV as a media player."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(self, coordinator: TitanOSCoordinator) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, None)

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return off, playing in live TV, otherwise on."""
        if self.coordinator.data.is_on is None:
            return None
        if not self.coordinator.data.is_on:
            return MediaPlayerState.OFF
        if self.coordinator.data.activity == "watchtv":
            return MediaPlayerState.PLAYING
        return MediaPlayerState.ON

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Offer stop and channel stepping only in live TV."""
        options = self.coordinator.config_entry.options
        features = MediaPlayerEntityFeature(0)
        if options.get("keys_verified"):
            features |= MediaPlayerEntityFeature.VOLUME_STEP
            # Standby must remain callable even when power is unknown.
            features |= MediaPlayerEntityFeature.TURN_OFF
            if (
                options.get("mute_state_verified")
                and self.coordinator.data.muted is not None
            ):
                features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if options.get("wol_verified") and self.coordinator.config_entry.data.get(
            CONF_MAC
        ):
            features |= MediaPlayerEntityFeature.TURN_ON
        if self.coordinator.dial_apps:
            features |= MediaPlayerEntityFeature.PLAY_MEDIA
            features |= MediaPlayerEntityFeature.BROWSE_MEDIA
        return features

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        """Return whether the TV is muted."""
        return self.coordinator.data.muted

    @property
    @override
    def source(self) -> str | None:
        """Return what the TV shows."""
        return _ACTIVITY_SOURCES.get(self.coordinator.data.activity or "")

    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Launch an opted-in registered DIAL app, with no power-state optimism."""
        if media_type != MediaType.APP or media_id not in self.coordinator.dial_apps:
            raise HomeAssistantError("Application is not a validated DIAL registration")
        if self.coordinator.dial is None:
            raise HomeAssistantError("DIAL is not configured")
        await self.coordinator.async_command(self.coordinator.dial.launch(media_id))

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Show only detected registrations; not the complete Titan app catalog."""
        return BrowseMedia(
            title="Local DIAL apps",
            media_class=MediaClass.DIRECTORY,
            media_content_id="dial",
            media_content_type="apps",
            can_play=False,
            can_expand=True,
            children=[
                BrowseMedia(
                    title=app,
                    media_class=MediaClass.APP,
                    media_content_id=app,
                    media_content_type=MediaType.APP,
                    can_play=True,
                    can_expand=False,
                )
                for app in self.coordinator.dial_apps
            ],
        )

    @override
    async def async_turn_on(self) -> None:
        """Wake the TV."""
        await self.coordinator.async_turn_on()

    @override
    async def async_turn_off(self) -> None:
        """Put the TV into standby."""
        await self.coordinator.async_turn_off()

    @override
    async def async_volume_up(self) -> None:
        """Raise the volume by one step."""
        await self.coordinator.async_command(
            self.coordinator.client.send_key("VolumeUp")
        )

    @override
    async def async_volume_down(self) -> None:
        """Lower the volume by one step."""
        await self.coordinator.async_command(
            self.coordinator.client.send_key("VolumeDown")
        )

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute with the remote's mute key, which toggles."""
        if self.coordinator.data.muted is None:
            raise HomeAssistantError(
                "Mute state unknown; use explicit remote Mute toggle"
            )
        if self.coordinator.data.muted == mute:
            return
        await self.coordinator.async_command(self.coordinator.client.send_key("Mute"))
        await self.coordinator.async_request_refresh()
