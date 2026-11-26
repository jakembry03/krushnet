# scripts/

## `router_test_resolver.py` (Phase 0, throwaway)

Answers the Phase 0 router question: when the router's DNS is set to alfred, do queries reach alfred **from each client's own IP** (direct, so per-device attribution works) or **all from the router's IP** (proxied)?

The script logs `time  source-IP  type  name` for each query, forwards it to Quad9 over **plain UDP**, and prints a count per source IP when you stop it. Shortcuts that are fine for a short test but not for real use: unencrypted upstream, UDP only (no TCP), no cache. Delete the script once the result is recorded in `docs/plan.md`.

Its only dependency is `dnslib`, declared inline (PEP 723), so `uv run` installs it in a temporary environment. No project setup is needed.

### Try it locally (no privileges)

```bash
uv run scripts/router_test_resolver.py            # listens on 127.0.0.1:5300
# in another terminal, e.g.:
dig @127.0.0.1 -p 5300 example.com                # dig is in the `bind` package on Arch
```

### Run it on alfred

Run these yourself. The script never needs root; `systemd-run` only grants it `CAP_NET_BIND_SERVICE` so it can bind port 53.

1. **Find alfred's LAN IP** and check port 53 is free on it. Ubuntu's `systemd-resolved` binds only `127.0.0.53`, so the LAN IP should be free:
   ```bash
   ip -4 addr show                       # note the LAN address, e.g. 192.168.1.50
   sudo ss -ulpn 'sport = :53'           # nothing should be on the LAN IP
   ```
2. **Firewall:** if `sudo ufw status` says active, allow DNS from the LAN for the test:
   ```bash
   sudo ufw allow from 192.168.1.0/24 to any port 53 proto udp
   ```
3. **Warm uv's cache** as your normal user, so the privileged run doesn't need to download anything:
   ```bash
   cd ~/krushnet && uv run scripts/router_test_resolver.py --help
   ```
4. **Start it** (replace the IP). It runs as your user with only the one capability, and Ctrl-C stops it and prints the summary:
   ```bash
   sudo systemd-run --uid="$USER" --gid="$(id -gn)" --pty --same-dir \
     -p AmbientCapabilities=CAP_NET_BIND_SERVICE \
     "$(command -v uv)" run scripts/router_test_resolver.py --listen 192.168.1.50:53
   ```
5. **Sanity check** from another machine: `dig @192.168.1.50 example.com` should answer, and a line should appear in the log.

### The test

1. In the My Spectrum app: **Advanced Settings → DNS Server → Manage DNS**. Set both entries to alfred's LAN IP.
2. Reconnect a client (toggle Wi-Fi) and check which DNS server it was given:
   - Linux: `resolvectl status`
   - Windows: `ipconfig /all`
   - Phone: Wi-Fi network details
3. Browse a little on that client and watch the log.
4. Read the result:
   - Client shows **alfred's IP** as DNS, and log lines carry the **client's own IP** → **direct**.
   - Client shows **192.168.1.1**, and log lines all come from the **router's IP** → **proxied**.
5. Note whether the client also lists **IPv6 DNS servers** (Phase 0 item 2). If it does, some lookups go over IPv6 and skip alfred entirely.
6. **Put the router back on "Use Spectrum DNS" before stopping the script.** While the router points at alfred, stopping the script takes the apartment's DNS down.
7. Ctrl-C the script, then copy the summary into "Phase 0 results" in `docs/plan.md`. If you opened the firewall in step 2, close it again: `sudo ufw delete allow from 192.168.1.0/24 to any port 53 proto udp`.
