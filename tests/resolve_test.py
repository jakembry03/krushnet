import socket
from app.validators import is_valid_ip
from app.main import resolve_host

def is_valid_ip_test(host: str):
    ip = resolve_host(host)
    print(ip)

is_valid_ip_test("scanme.nmap.org")
