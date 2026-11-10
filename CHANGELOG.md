# Changelog

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
