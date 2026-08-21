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

    My idea is to use the service_map as a reference for expected services. Change the output that the program gives when scanning to show the expected services for each port. Then use that 
    service map as a reference for banner grabbing. If the service is passive, then have it passively receive the banner, if the service is active then configure what the scanner would need to do to retrieve that banner. Not a super complicated setup. Will work on this first and then move on to the rest of the functionality.

v0.3.0
1. Store results in SQLite database and read results from the database when outputting
2. Grab OS and host information from the device if available

v0.4.0
1. Working command line functionality
    Commands and flags, using krushnet as the executable command instead of python
2. 




---

CLI KrushNet is a port scanner. The Web KrushNet will be the full Network Operations center. The functionality I want to build into the CLI version is for the scanner to be able to scan any device or network and produce a comprehensive report of the device. It should be able to detect open ports, the services running on that port, possible Operating System, the hostname if present, the IP address etc. Once the web version gets more further developed, the program will be more about detection and being able to see devices on the local network, see information about them using the same logic, and also provide monitoring and limited control of the device at the network level to the admin user of the web portal. The ability to control what type of traffic is allowed through the network and others. I think it would be cool to create an agent that I could deploy on certain devices that would record full network diagnostics that would relay to the web portal. And the admin user would be able to remote onto the device and alter things about the device from the web portal. It would be a ton of cool features from the web portal that I would love to work in the future versions. Will work on that as the program gets more developed.


