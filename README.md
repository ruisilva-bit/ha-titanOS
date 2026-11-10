# Philips Titan OS TV — Home Assistant

Local control for Philips Titan OS TVs, based on
[ksooo/ha-philips-titanos](https://github.com/ksooo/ha-philips-titanos).
Target model: **Philips 55PUS8079/12 / TPN246E**.

## Version 1.0.0: production controls, English interface

**Normal remote commands no longer require test mode or a “keys validated” flag.**
Remote/media controls are enabled by default. Wake-on-LAN is enabled when the
existing pairing provides a suitable MAC. No new pairing or credential migration
is required. Existing `remote_testing`, `keys_verified` and `wol_verified` flags
no longer block normal use.

Production defaults are a software configuration, **not a claim that every
feature has been physically verified on the target TV**. The software has been
exercised with Home Assistant 2026.10.1 and Python 3.14.9; the TV address and the
installed HA version have not been supplied. See [acceptance](docs/ACCEPTANCE.md).

All bundled UI text, documentation and dashboard examples are in English.
English text is also supplied for the existing Portuguese/German locale entries;
this does not change the language of Home Assistant itself.

## Features

- JointSpace v6 HTTPS/Digest pairing without a Cast TCP 8009 prerequisite.
- Navigation, Home, Back, OK, Source, volume steps, mute toggle, channel keys,
  digits, colours and playback keys through the remote entity.
- Native [remote dashboard card](examples/remote-card.yaml): no custom frontend
  dependency, with navigation pad, power confirmation, digits and media controls.
- Guarded Standby: authenticated preflight, concurrent-call serialization and
  no automatic repeat after an ambiguous success/timeout.
- Async Wake-on-LAN, validated MAC and configurable IPv4 broadcast.
- Honest power state: `unknown` when there is no reliable screen-power signal;
  `unavailable` on communication failure; no false “on” from HTTP 200.
- Optional Ambilight discovered from TV features/styles/menu; no automatic writes
  to restore lights after wake.
- Optional local DIAL discovery and launch for detected YouTube, Netflix and
  AmazonInstantVideo registrations. Apps appear in the media browser only when
  enabled and detected. DIAL `running` is not a foreground-app or power signal.
- 30-second base polling, bounded failure backoff, recovery and reauthentication.
- LAN connectivity entity and allowlisted diagnostics, without credentials,
  IP/MAC/serial or complete response bodies.

These are implemented commands, not a hardware-compatibility certification.
Unsupported or refused commands surface errors rather than simulated execution.

## Install or update without losing pairing

1. Use **Home Assistant 2026.10.0 or later**; tests use 2026.10.1. Compatibility
   with an unknown installed version must still be checked.
2. Create a Home Assistant backup and separately retain the complete current
   `/config/custom_components/philips_titanos` folder. Backups contain secrets:
   keep them private.
3. Disable automatic updates from the original HACS repository. Only one
   repository should manage the `philips_titanos` domain.
4. Temporarily disable the integration while replacing its folder. Copy only
   `custom_components/philips_titanos` from this release into
   `/config/custom_components/philips_titanos`. Keep the old folder outside
   `custom_components` as a backup.
5. Restart Home Assistant during an approved maintenance window, then re-enable
   the **existing entry**. Do not delete it, edit `.storage` or pair again.
6. For an IP change, use **Reconfigure**. The serial must match the existing TV.

The domain, Config Entry version 1, credential keys and entity unique IDs are
preserved. Optional-feature preferences from version 0.2.0 are read compatibly.
Saving the new options replaces obsolete test flags without touching credentials.

### HACS

Add `https://github.com/ruisilva-bit/ha-titanOS` as a custom **Integration**
repository and select the desired published version. Do not leave the original
repository managing the same directory. Review release notes before updating.

## Remote dashboard

Find the actual `remote` and `media_player` IDs in **Settings → Devices & services**.
Add a **Manual card** to a dashboard, paste `examples/remote-card.yaml`, and replace
`remote.your_tv` and `media_player.your_tv` with those IDs.

Alternatively, generate the card with exact IDs in a development checkout:

```bash
uv run python tools/build_dashboard.py \
  --remote remote.living_room_tv \
  --player media_player.living_room_tv \
  --output remote-card.yaml
```

No server-side frontend resource registration is required. The card includes
power confirmations and disables hold/double-tap actions to avoid accidental
repeated toggles. Runtime errors still apply if firmware rejects a key. Its media
control card provides access to detected DIAL apps through the media browser.
Dashboard YAML/service actions are validated in automated tests; visual rendering
in the user's HA frontend has not been observed.

### Applications and Plex

Enable **Local DIAL applications** to discover supported registrations. Then use
the media browser or an explicit action:

```yaml
action: media_player.play_media
target:
  entity_id: media_player.your_tv
data:
  media_content_type: app
  media_content_id: YouTube
```

Only detected app IDs can be launched. **Plex is not implemented or confirmed**
for this TV; installing it on the TV does not prove a local launch API exists.
There are no fake Plex buttons, hard-coded app URLs or unreliable HDMI macros.
Matter may supply additional controls that can be used in a dashboard, but this
integration does not automatically merge Matter entities or assume their abilities.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| Enable remote and media controls | On | Normal explicit user commands; switch off to disable them. |
| Enable Wake-on-LAN | On | Requires a stored suitable MAC; sending a packet is not proof of wake. |
| Local DIAL applications | Off | Read registrations and allow explicit launch on the local TV. |
| Ambilight | Off | Also requires TV feature/style support; enable only if applicable. |
| Trust the TV powerstate reading | Off | Enable only if ON/standby reads actually follow the physical screen. |
| Trust the TV mute reading | Off | Enable only if it follows the physical remote, not stale API echoes. |
| WOL IPv4 broadcast | 255.255.255.255 | Use the TV VLAN's broadcast when needed and allowed. |

A mute **toggle** is always available through the remote. Idempotent media-player
mute is exposed only with a trusted, available state. Absolute volume, direct
HDMI selection, current channel and foreground-app reporting are not advertised.
Settings reload the entry, preserving pairing. No TV-control write happens just
because the entry is loaded or options are saved.

## Power behaviour and safety

Standby can be a toggle on this firmware. The integration must not discard it
because Cast is closed, but sending it blindly twice could wake a TV instead.
After one Standby without reliable confirmation, repeated Standby calls are
blocked, even after timeout. **This safety latch remains in production.** Check
the physical screen before manually reloading the integration to rearm it; never
use reload as an automatic retry loop.

A WOL command records `waking`, not a fabricated on state. Network silence cannot
distinguish deep standby, disconnected power or a network fault. The deep-standby
state remains reserved until an explicit reliable signal exists.

If the TV exposes no trustworthy power state, use the remote buttons independently
of the media player's `unknown` screen state. No production setting can create
hardware telemetry that the firmware does not provide.

## Read-only hardware diagnosis

From a trusted terminal on the TV LAN:

```bash
python3 tools/probe_tv.py TV_IP
python3 tools/probe_tv.py TV_IP --paired
```

`--paired` requests the existing device ID/auth key through masked prompts. It
does not save secrets, pair again or issue writes. Never paste credentials, QR
codes or `.storage` dumps into chat/issues. The report contains only safe statuses.

Compare observations while the screen is physically on, in quick standby and
in prolonged standby. Ports, HTTP success, MQTT login and DIAL `running` do not
prove a lit screen. Obtain approval before disruptive commands or network changes.

## Network and security

- Everything implemented addresses the configured TV locally: JointSpace, WOL
  and optional DIAL. No Philips/Titan cloud or YouTube Lounge dependency.
- MQTT was researched, not implemented. The reference app inventory uses a
  `proxy` cloud request, so it cannot be promised as an offline catalogue.
- JointSpace uses its self-signed certificate without SAN, as in the original
  client. **Server identity is not verified and certificate pinning is not
  implemented. An attacker on the LAN could intercept pairing or tamper with
  commands/responses.** Use a trusted, isolated LAN; never expose these ports.
- Redirects are disabled, diagnostic response bodies are not logged, and writes
  are not retried automatically. Requests are serialized and spaced by ≥0.7 s.
- Firmware may still wedge under load; stop probing if TLS becomes unreliable.
- WOL across VLANs and Matter IPv6/multicast depend on your network. No firewall,
  router, firmware, factory-reset or security configuration is changed by this code.

## Development and validation

```bash
uv sync --locked --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q --junitxml=test-results.xml
```

Python is pinned in `.python-version`; runtime dependencies are supplied by HA.
CI runs these checks plus hassfest and HACS validation. See
[validation evidence](docs/VALIDATION.md), [research](docs/RESEARCH.md), and
[release notes](CHANGELOG.md). Simulated tests are not physical TV evidence.

## Rollback

Disable the entry, restore the complete previous `philips_titanos` directory,
restart HA in an approved window and re-enable the same entry. Do not delete the
entry or its credentials. If required, restore the private full HA backup.
Review the owning HACS repository before re-enabling updates. Returning to the
original upstream may restore its known dependency on Cast 8009; returning to
0.2.0 restores its experimental control gates.

## Licensing

Imported code remains **Apache-2.0** under `LICENSE.upstream`; `NOTICE` identifies
its source and modified files. The repository's original MIT `LICENSE` is retained
and does not relicense imported Apache material. Other projects were studied as
protocol references; no code was copied from a project without an identified
license.
