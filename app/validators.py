import ipaddress

def is_valid_ip(value: object) -> bool:
    if not isinstance(value, str):
        return False

    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

    
