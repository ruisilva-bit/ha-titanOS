# Changelog

## Unreleased

### Fixes

- Portuguese (`pt`) interface restored; it had been a copy of the English text.
- Ambilight: a failed menu read is retried on the next poll instead of leaving the
  off switch and menu entries missing until reload.
- Remote: every key is validated before the first one is sent; repeats are
  limited to 1–10 and delays to 0–2 s.
- Pairing: an interface without a MAC no longer aborts the flow.
- Removed unused code: the Cast-port probe, channel-list helpers and an unused
  menu reader.

### Dashboard

- Remote card rebuilt with the HACS **button-card** frontend resource: 758 → 323
  lines. The generator is the single source for `examples/remote-card.yaml`.
- Options, Info, Stop, Rewind and Forward were removed from the card.

## 1.0.0

### Production defaults

- Enable normal remote/media controls without `remote_testing` or `keys_verified`.
- Enable WOL by default when a suitable MAC exists, without `wol_verified`.
- Add explicit control/WOL opt-outs; direct service calls respect them.
- Preserve existing pairing data, unique IDs and entry version.
- Carry forward optional DIAL/Ambilight and power/mute trust preferences.
- Retain unknown power states, authenticated Standby preflight, duplicate latches,
  no write retries, serialized requests and LAN-only operation.

### English interface and remote card

- Supply English text for all bundled interface locales and documentation.
- Add a native remote dashboard card, entity-aware generator and HA action tests.
- Keep media-browser apps restricted to detected local DIAL registrations.
- No unverified Plex, direct-HDMI or current-foreground-app capability is claimed.

### Remaining acceptance boundaries

Physical control effects, screen-power telemetry and wake delivery on the
55PUS8079/12 still require observation. No Home Assistant deployment or TV
commands are part of repository preparation. Self-signed JointSpace TLS still
lacks server identity verification/pinning; use a trusted isolated LAN.

## 0.2.0

Initial local-control implementation with Cast-independent pairing, conservative
power evidence, WOL, opt-in DIAL/Ambilight, diagnostics, experimental key gates and
99 automated tests. See the preserved validation history for its exact revision.
