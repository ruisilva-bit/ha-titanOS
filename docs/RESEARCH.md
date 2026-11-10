# Local protocol research

## Target and existing evidence

Philips **55PUS8079/12**, Titan OS, **TPN246E**. The user obtained HTTP 200
from `https://TV_IP:1926/6/system`, found Cast TCP 8009 inaccessible, and paired
successfully after removing the upstream Cast/standby prerequisite.
These are user-reported observations, not new probes from this checkout.
No TV address was supplied to the implementation environment.

## Sources and reuse

| Source | Reviewed revision | License / use |
|---|---|---|
| [ksooo/ha-philips-titanos](https://github.com/ksooo/ha-philips-titanos) | `d23ef23d98d6ce9a54371a147d140494e3152fc3` | Apache-2.0; implementation and tests imported with attribution. |
| [bedirhanyildirim/philips-titan-os-55pml9019-remote](https://github.com/bedirhanyildirim/philips-titan-os-55pml9019-remote) | `4db4cb4d109030ccb194413665aa918270584c58` | MIT; protocol reference, not proof for the target model. |
| [daCream87/uc-philips-titanos](https://github.com/daCream87/uc-philips-titanos) | `cf0207a0261288e5e0ebb2af248f5a160a4e99f8` | No license identified at review; no code copied. |

The upstream maintenance notes describe a different model and cannot establish
55PUS8079 compatibility. Upstream issue #1 was reviewed; no comments were returned.
The absence of search results for open pairing/standby PRs is not proof none exist.
Never reproduce secret values embedded in reference code or test fixtures.

## Findings by mechanism

### JointSpace v6

HTTPS 1926 with Digest authentication and stored device credentials is the
implemented local control path. TCP 8009 is not a valid prerequisite for pairing,
issuing Standby, or declaring screen power. The API can answer while the panel is
off. Authentication, communications health, requested intent and observed power
must be represented separately.

The client serializes requests and spaces them by at least 0.7 seconds. Writes
are never retried automatically after timeout. Standby is treated as a possible
toggle: preflight checks authenticate before writing, and an in-memory latch is
set before the request can reach the TV. No unconditional post-wake restoration
of volume, channel or Ambilight is performed.

Power/mute endpoint results remain untrusted unless the user explicitly enables
their use after a physical comparison. Deep standby is not inferred from network
silence. Channel database writes, direct HDMI selection and absolute volume are
not advertised as known-compatible features.

### Wake-on-LAN

Uses the suitable MAC from the existing paired system data, with asynchronous
UDP broadcast. Network/VLAN delivery and wake capability remain model/firmware
questions. Sending a valid packet records intent, not an observed lit screen.

### DIAL

The local DIAL app service uses HTTP port **56789**. The implementation queries
known candidates `YouTube`, `Netflix`, `AmazonInstantVideo`, parses XML
registrations, and only exposes detected candidates when enabled. Discovery is
refreshed separately from JointSpace and does not impose a cloud dependency.
A registration or `running` result is not proof of foreground focus or power.
Launch completion on this TV has not been observed. **Plex has not been added**:
no compatible local registration/launch protocol has been confirmed.

### MQTT and app inventory

The remote reference describes MQTT/TLS (including port 36669), HDMI and app
launch mechanisms on another Philips model. Its inventory uses a Titan `proxy`
cloud request; that is not an offline catalogue. The mechanism is researched,
not implemented or certified here. Firmware ports, authentication and command
schemas must be observed on the target before adding it. Do not copy embedded
credentials or brute-force the TV.

### Matter

Philips documents “TV Control with Matter” for the 2024 8079 series. The user
confirmed the menu, tried Matter and reported limited functions. Exact clusters,
entities and actions were not supplied. Matter may complement local controls;
it is not evidence that HA supports a full remote or Plex launch.

- [Philips Matter guidance](https://tv-sound-monitors.philips.com/s/article/What-is-Matter-and-how-can-I-use-it-on-the-Philips-Titan-OS-TV?language=en_US)
- [Home Assistant Matter](https://www.home-assistant.io/integrations/matter/)

Matter over Ethernet/Wi-Fi does not itself require a Thread adapter. VLAN,
IPv6 and multicast changes require separate authorization and are outside this
release.

## Security boundary

JointSpace retains the upstream self-signed TLS behaviour (`ssl=False`); there
is no server identity verification or pinning. This leaves a LAN MITM risk during
pairing/control and must not be disguised as a production security guarantee.
Use a trusted isolated LAN and no public port forwarding. Credentials are not
logged or included in allowlisted diagnostics. HTTP redirects are disabled.

## Version 1.0.0 policy

Normal explicit remote commands no longer require experimental validation flags.
The separate production opt-out switches are `enable_controls` and `enable_wol`.
Firmware-specific read trust and optional features still default off. This removes
a usability gate, not the need for physical acceptance. Existing pairing data,
domain, entry version and unique IDs are unchanged.
