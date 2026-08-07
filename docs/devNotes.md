v0.1.0 = Basic single target port scanner
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

v0.2.0
1. Capture banners
    banner = receive all
    if banner has a value
        print banner
2. Have functionality for all major banners, HTTP/HTTPS and others.
    if port == 80 or 443 then send http header or https header
3. Scan an entire network
    Would need a function that determines what format the given host is in. If it is in hostname, ip address, or network interface.
    If hostname or IP, scan runs normally after resolving the name, if network interface, then the scan runs for the network
    Then the same would be for a range of IP addresses

v0.3.0
1. Store results in SQLite database and read results from the database when outputting
2. Grab OS and host information from the device if available

v0.4.0
1. Working command line functionality
    Commands and flags, using krushnet as the executable command instead of python
2. 


