#!/usr/bin/python
import argparse
from sys import exit
from queue import Queue

try:
    import socket
    import threading
    import scapy.all
    import requests
except ModuleNotFoundError as err:
    exit("requirements not installed. run: pip3 install -r requirements.txt")

# ascii color codes
GREEN = "\033[0;32m"
RESET = "\033[0;0m"
RED = "\033[0;31m"


__version__ = "2.3"


def argsParser():
    parser = argparse.ArgumentParser(prog='PROG')
    subparser = parser.add_subparsers(dest="command")
    subparser.required = True

    parser_a = subparser.add_parser("scan", help="find open ports.")
    parser_a.add_argument("-T", "--target", dest="TARGET",
                        type=str, help="specify the target IP address",
                        required=True)
    parser_a.add_argument("-p", "--port", dest="PORTS", nargs="+",
                        type=int, help="specify one or more ports",
                        )
    parser_a.add_argument("-r", "--range", dest="RANGE",
                        type=str, help="range of ports to be scanned (e.g. 1-1024)",
                        )
    parser_a.add_argument("-t", "--threads", dest="THREADS",
                        default=100, type=int, help="number of threads (default: 100)")

    parser_b = subparser.add_parser("get", help="get info. (general, version)")
    parser_b.add_argument("info", choices=["general", "version"])

    parser_c = subparser.add_parser("local", help="scan local network.")
    parser_c.add_argument("-s", "--scan", required=True, dest="network", type=str,
                        help="scan local devices that are connected to the network.")

    return parser.parse_args()


def scan_network(ip_, outputs):
    """
    return IPv4 of all connected devices to the network as well as their MAC address.
    """

    # verbose turned off by default.
    scapy.all.conf.verb = 0

    # send ARP request
    request = scapy.all.ARP()

    ip = ip_.rpartition(".")[0] + ".0"  # set network address

    # specify network address in CIDR notation
    request.pdst = i = f"{ip}/24"

    broadcast = scapy.all.Ether()

    broadcast.dst = "ff:ff:ff:ff:ff:ff"

    request_broadcast = broadcast / request

    hosts = scapy.all.srp(request_broadcast, timeout=1)[0]

    for host in hosts:
        addr = host[1].psrc
        mac_addr = host[1].hwsrc
        try:
            hostname = socket.gethostbyaddr(addr)[0]
        except socket.herror as err:
            hostname = "UNKOWN"
        data = [addr, hostname, mac_addr]
        if data not in outputs:
            outputs.append(data)
        else:
            continue


class PortScanner(threading.Thread):
    def __init__(self, ip, _queue):
        threading.Thread.__init__(self)
        self.ip = ip
        self._queue = _queue

    def run(self):
        global GREEN
        global RESET
        """
        it keeps looping as long as there are ports available to scan
        """
        while not self._queue.empty():
            port = self._queue.get()
            try:
                # if a connection was successful, the port will be printed.
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # create an internet tcp sock
                sock.connect((self.ip, port))
                print(f"{GREEN} [+]{RESET} {self.ip}:{port}")
            except:
                # ports that are not open are skipped.
                continue


def fill_queue(_list, _queue):
    """turns a list of ports into a queue"""
    for item in _list:
        _queue.put(item)


def manager(_range, ip, _queue):
    """
    takes care of threads and speeds up port scanning.
    """
    global RED
    global RESET
    threads = []
    for i in range(_range):  # Set how many threads to run.
        thread = PortScanner(ip, _queue)
        threads.append(thread)

    for thread in threads:
        thread.start()

    try:
        for thread in threads:
            thread.join()  # wait till threads finish and close.
    except KeyboardInterrupt:
        print(f"{RED}exiting..{RESET}")


def ascii_banner():
    print("""\033[0;32m
         ///              
        / SCANET 
       ///\033[0;0m
    """)


def main():
    args = argsParser()

    if args.command == "get":
        if args.info == "general":
            host = socket.gethostname()
            ipv4 = socket.gethostbyname(host)
            if ipv4[:3] == "127":
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ipv4 = s.getsockname()[0]
            gateway = ipv4.rpartition(".")[0] + ".1"
            try:
                public_ip = requests.get("https://ipinfo.io/json").json()["ip"]
            except:
                # if the host is not connected to the internet.
                public_ip = "Not available"
            ascii_banner()
            print(f"""
            Hostname: {host}
            Gateway: {gateway}
            Private IPv4: {ipv4}
            Public IPv4: {public_ip} 
            """)

        elif args.info == "version":
            global __version__
            ascii_banner()
            print("current version is:", __version__)

    elif args.command == "local":
        results = []
        try:
            for i in range(4):
                scan_network(args.network, results)
            for i in results:
                print("{:16} | {:40} | {:17}".format(*i))
        except PermissionError as err:
            print("Permission denied. are you root?")
    elif args.command == "scan":
        try:
            if args.RANGE:
                RANGE = [int(i) for i in args.RANGE.split("-")]
                data = (args.TARGET, RANGE, args.THREADS)

            elif not args.PORTS and not args.RANGE:
                print("[-] No ports specified! use '--help' for help")
            else:
                data = (args.TARGET, args.PORTS, args.THREADS)

        except:
            print("[-] Error. use '--help' for help")

        IP, ports, threads = data  # unpacking the returning tuple of data

        try:  # check if the value is a range or a list
            ports = range(ports[0], ports[1] + 1)
        except IndexError:
            pass

        running_threads = threads  # number of threads to run
        # Queue class is to exchange data safely between multiple threads.
        # it also prevents threads from returning duplicates.
        queue = Queue()
        fill_queue(ports, queue)  # it takes either a list or a range of ports
        manager(running_threads, IP, queue)

        print("\nscanning finished.\n")

    else:
        print("use -h for help")


if __name__ == "__main__":
    main()
