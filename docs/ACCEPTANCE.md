# Acceptance matrix

Production-mode software must not be confused with physical-TV certification.
No TV address or actual installed HA version has been supplied to this checkout.

| Requirement | Software contract | Physical target evidence |
|---|---|---|
| Pair with TCP 8009 closed | Cast is not a pairing prerequisite; regression test. | User reports successful pairing with that gate removed. |
| Preserve pairing | Domain, entry version 1, credentials and unique IDs retained. | Update/reload must still be observed on the user's HA. |
| Detect lit screen | Unknown unless trustworthy powerstate is enabled and available. | Not verified; HTTP 200 is insufficient. |
| Standby | Authenticated preflight; serialized single write; latch before ambiguous completion. | Not verified; user hit the former local validation gate before a write. |
| Wake | Async WOL to validated stored MAC; intent is not confirmation. | Delivery/wake not verified. |
| Volume steps | Normal remote/media services enabled without test mode. | Physical effect not verified. |
| Mute | Remote toggle; media mute requires a trusted reading. | Physical effect/read accuracy not verified. |
| Navigation/Home/Back/OK | Allowlisted JointSpace keys and aliases. | Per-key effect not verified. |
| Ambilight | Optional, discovered feature/style/menu support. | Not verified on target. |
| Apps | Optional DIAL; only detected YouTube/Netflix/AmazonInstantVideo. | Registration and launch not verified. |
| Plex | No unsupported shortcut or launch claim. | Not implemented/confirmed. |
| Direct HDMI | Source menu key; no invented direct-input mapping. | Direct selection not confirmed. |
| Dashboard | Native card YAML, registered-service payload tests and generator. | Frontend rendering/mobile layout not observed on the user's HA. |
| English | English UI for every bundled locale, docs and examples. | HA's own core language remains outside integration control. |
| Security | Secrets excluded from diagnostics; serialized requests; no write retries. | Server TLS identity is not verified; trusted LAN is required. |
| Matter | Can coexist; no automatic entity merge. | User tried it and found limited functions. |

## Physical sign-off still required

With an approved maintenance window, compare observations with the actual screen
on, in quick standby and prolonged standby. Use a read-only baseline first.
Check volume/mute/navigation individually and note accepted/refused keys. Obtain
permission before Standby/WOL or other disruptive commands. Stop on unreliable
TLS; do not turn an ambiguous write into an automatic retry.

Only enable trust in power/mute readings when they track the physical remote.
Only enable DIAL/Ambilight after checking applicability. Verify reconnect,
authentication failure, HA restart, entity availability and rollback without
re-pairing. Record firmware/HA versions without credentials or serial dumps.
A successful CI run cannot replace these acceptance observations.
