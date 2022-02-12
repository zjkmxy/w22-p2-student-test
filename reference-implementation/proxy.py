#!/usr/bin/env python3

import socket
import sys
import time
from struct import *
import signal, os

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

if len(sys.argv) != 5:
    print("ERROR: expected exactly 4 parameters:", file=sys.stderr)
    print("    %s <LOCAL_IP> <LOCAL_PORT> <REMOTE_IP> <REMOTE_PORT>" % sys.argv[0], file=sys.stderr)
    exit(1)

src = (sys.argv[1], int(sys.argv[2]))
dst = (sys.argv[3], int(sys.argv[4]))

needStop = []
def handler(signum, stuff):
    needStop.append(1)

sock.bind(src)

sourceAddr = None

while len(needStop) == 0:
    try:
        data, addr = sock.recvfrom(1024)

        if sourceAddr is None:
            sourceAddr = addr

        if addr == sourceAddr:
            to = dst
        else:
            to = sourceAddr

        if addr == sourceAddr:
            sys.stdout.write("%d\n" % len(data))
            sys.stdout.flush()
            
        time.sleep(0.01)

        sock.sendto(data, to)

    except socket.error:
        pass

    except KeyboardInterrupt:
        needStop.append(1)
