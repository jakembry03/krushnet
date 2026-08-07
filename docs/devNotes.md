V 0.1.0 = Basic single target port scanner
1. Initialize the Scanner
2. Take host and port input (single, list, range)
3. Scan the target
4. Store formatted reuslts
    Store it as a list of dictionaries
    open_ports = [
        {port: open},
        {port: open},
        {port: open},
    ]
    
    for port in ports:
        result = s.connect_ex((host, port))
        if result == 0:
            open_ports.append({port: "open"})

5. Output complete formatted results

V 0.2.0
1. Capture banners
    banner = receive all
    if banner has a value
        print banner
2. Scan an entire network

