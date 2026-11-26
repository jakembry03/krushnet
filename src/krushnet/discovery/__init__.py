"""Device discovery: ARP scanning, passive ARP/mDNS/DHCP listening, OUI lookup.

Parses only the fields needed to identify devices; never stores packet
payloads (hard rule 1). Runs with CAP_NET_RAW only (hard rule 2).
"""
