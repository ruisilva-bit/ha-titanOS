"""Generate the remote dashboard card for the Philips Titan OS TV.

The card uses the custom ``button-card`` frontend resource (install it from
HACS, frontend category). This generator is the single source of truth for
``examples/remote-card.yaml``; the test suite fails if the two drift apart.
"""

import argparse
from pathlib import Path
import re

import yaml

CARD = "custom:button-card"


class FlowMap(dict):
    """A mapping written on one line; keeps action blocks readable."""


class _Dumper(yaml.SafeDumper):
    """Emit FlowMap as flow style; every button stays self-contained."""

    def ignore_aliases(self, data):
        # Anchors inside one-line blocks are noise; repeating values is cheap.
        return True


_Dumper.add_representer(
    FlowMap,
    lambda dumper, data: dumper.represent_mapping(
        "tag:yaml.org,2002:map", data, flow_style=True
    ),
)
NO_ACTION = FlowMap(action="none")
ICON_STYLE = FlowMap(
    card=[FlowMap(height="52px")], icon=[FlowMap({"--mdc-icon-size": "26px"})]
)
BLANK_STYLE = FlowMap(card=[FlowMap(visibility="hidden")])
POWER_CONFIRMATION = FlowMap(text="Send this power command to the TV?")
COLOURS = (
    ("Red", "#e53935", "RedColour"),
    ("Green", "#43a047", "GreenColour"),
    ("Yellow", "#fdd835", "YellowColour"),
    ("Blue", "#1e88e5", "BlueColour"),
)


def build_card(remote: str, player: str) -> dict:
    """Use actual entity IDs; never register or expose a new service."""
    if not re.fullmatch(r"remote\.[a-z0-9_]+", remote):
        raise ValueError("Expected a remote entity ID")
    if not re.fullmatch(r"media_player\.[a-z0-9_]+", player):
        raise ValueError("Expected a media_player entity ID")

    # Shared objects let yaml.safe_dump emit anchors instead of repeating them.
    target = FlowMap(entity_id=remote)

    def tap(service: str, data: dict | None = None, confirm: dict | None = None):
        action = FlowMap(action="perform-action", perform_action=service)
        action["target"] = target
        if data is not None:
            action["data"] = data
        if confirm is not None:
            action["confirmation"] = confirm
        return action

    def key(command: str) -> dict:
        return tap("remote.send_command", FlowMap(command=[command]))

    def button(action, name=None, icon=None, style=ICON_STYLE) -> dict:
        card = {"type": CARD}
        if name is not None:
            card["name"] = name
        if icon is not None:
            card["icon"] = "mdi:" + icon
        if name is None:
            card["show_name"] = False
        if icon is None:
            card["show_icon"] = False
        card |= {
            "show_state": False,
            "tap_action": action,
            "hold_action": NO_ACTION,
            "double_tap_action": NO_ACTION,
            "styles": style,
        }
        return card

    blank = button(NO_ACTION, style=BLANK_STYLE)

    def grid(cards: list[dict], columns: int = 3) -> dict:
        return {"type": "grid", "columns": columns, "square": False, "cards": cards}

    def colour(name: str, hex_colour: str, command: str) -> dict:
        style = FlowMap(
            card=ICON_STYLE["card"],
            icon=[FlowMap(color=hex_colour), FlowMap({"--mdc-icon-size": "26px"})],
        )
        return button(key(command), name=name, icon="circle", style=style)

    cards = [
        grid(
            [
                button(
                    tap("remote.turn_on", confirm=POWER_CONFIRMATION),
                    name="Wake",
                    icon="power-on",
                ),
                button(
                    tap("remote.turn_off", confirm=POWER_CONFIRMATION),
                    name="Standby",
                    icon="power-standby",
                ),
                button(key("Source"), name="Source", icon="video-input-hdmi"),
                button(key("Home"), name="Home", icon="home"),
            ],
            columns=4,
        ),
        grid(
            [
                button(key("Back"), icon="arrow-u-left-top"),
                button(key("CursorUp"), icon="chevron-up"),
                blank,
                button(key("CursorLeft"), icon="chevron-left"),
                button(key("Confirm"), icon="checkbox-marked-circle-outline"),
                button(key("CursorRight"), icon="chevron-right"),
                blank,
                button(key("CursorDown"), icon="chevron-down"),
                blank,
            ]
        ),
        grid(
            [
                button(key("VolumeDown"), icon="volume-minus"),
                button(key("Mute"), icon="volume-mute"),
                button(key("VolumeUp"), icon="volume-plus"),
                button(key("ChannelStepDown"), icon="minus"),
                button(key("ChannelStepUp"), icon="plus"),
            ],
            columns=5,
        ),
        grid(
            [
                button(key("Play"), icon="play"),
                button(key("Pause"), icon="pause"),
                button(key("WatchTV"), name="Live TV", icon="television"),
            ]
        ),
        grid(
            [
                *(button(key(f"Digit{i}"), name=str(i)) for i in range(1, 10)),
                blank,
                button(key("Digit0"), name="0"),
                blank,
            ]
        ),
        grid([colour(*c) for c in COLOURS], columns=4),
        {"type": "media-control", "entity": player},
    ]
    return {"type": "vertical-stack", "cards": cards}


def dump(card: dict) -> str:
    """Serialize compactly: action blocks on one line, shared objects anchored."""
    return yaml.dump(
        card,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=None,
        width=1000,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="remote.your_tv")
    parser.add_argument("--player", default="media_player.your_tv")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = dump(build_card(args.remote, args.player))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content)
