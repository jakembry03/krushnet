# 0005: Parse discovery traffic with our own byte parsers

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decider:** Jake

## Context

The discovery service captures ARP, DHCP and mDNS on alfred's LAN interface. From each frame it needs only a few facts:
- ARP: sender MAC and IP.
- DHCP: client MAC, hostname (option 12), and the address once granted.
- mDNS: the hostname a device announces for itself.

Every frame is untrusted (hard rule 4), and nothing else may be kept (hard rule 1). ADR 0002 picked scapy for discovery, but didn't say whether scapy should also *parse* the packets.

## Options

### Option A: Our own parsers over raw Ethernet frames, with mDNS via `dnslib`
- Pros:
  - About 300 lines, fully typed and checked with mypy --strict.
  - Every length field is checked explicitly.
  - Reads only the fields we use.
  - Easy to fuzz.
  - No new dependency, since `dnslib` is already used.
- Cons: code we own and maintain.

### Option B: Scapy's dissectors (`Ether()`, `ARP`, `DHCP`, `DNS`)
- Pros: less of our own code.
- Cons:
  - Untyped.
  - Slower.
  - Dissects far more of each packet than we need.
  - Its behaviour on malicious input is harder to reason about and test.

## Decision

Option A. `krushnet.discovery.parse_frame(frame: bytes) -> list[Observation]` is a pure function that never raises. Scapy is used only for capture and for sending ARP sweeps (PR 1.4).

These rules are part of the decision:
- **ARP:** only sender fields are used, and the ARP sender MAC must equal the Ethernet source MAC. A mismatch is proxy ARP or spoofing. Probes from `0.0.0.0` are skipped.
- **DHCP:**
  - Hostnames and `ciaddr` come only from client messages (DISCOVER, REQUEST, INFORM).
  - Addresses come from a server ACK's `yiaddr`, never from an OFFER and never from option 50 (requested IP).
  - The device is identified by `chaddr`.
- **mDNS:**
  - Only responses from port 5353 to the multicast group are used.
  - Of those, only A and AAAA records for `<single-label>.local` whose address equals the packet's own source IP. Bonjour sleep proxies announce other devices' names, and this rule stops those names being attached to the proxy.
  - PTR, SRV and TXT records are ignored.
- **Hostnames** must be strict UTF-8 with no control or format characters, at most 63 characters, and are rejected rather than truncated.
- **Unusable MACs** (multicast, broadcast, all-zero) and unusable IPs (unspecified, multicast, loopback, limited broadcast) are dropped.
- **Layers:**
  - At most one VLAN tag.
  - IPv4 fragments are ignored.
  - IPv6 packets with extension headers are skipped.
  - Frames over 9,216 bytes are ignored.

## Consequences

- `krushnet.discovery` joins `dns/`, `policy/` and `config` in mypy's strict set (CLAUDE.md updated).
- **Fuzz tests are seeded and use only the standard library.** They cover every truncation and every bit flip of each sample, plus random mutations and random payloads. They show the parsers raise nothing on their own; the guard in `parse_frame` is only a last line of defence.
- **Test samples are synthetic.** Real captures stay off the repo because they contain household device data. Jake's own capture can be replayed locally in PR 1.4.
- **What alfred can see is still unknown.** Unicast DHCP traffic (ACKs, renewals) may not reach it on a switched network. ARP sweeps cover addresses whatever happens. The Phase 0 tcpdump evening will confirm.
- **Possible additions later:** DHCP option 81 (FQDN) and IPv6 Neighbor Discovery.
