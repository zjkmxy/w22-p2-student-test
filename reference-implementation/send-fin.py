#!/usr/bin/env python3

import socket
import sys
import time
from struct import *

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

if len(sys.argv) != 7:
    print("ERROR: expected exactly 6 parameters:", file=sys.stderr)
    print("    %s <DST_IP> <DST_PORT> <SRC_IP> <SRC_PORT> <SEQ> <ID>" % sys.argv[0], file=sys.stderr)
    exit(1)

dst = (sys.argv[1], int(sys.argv[2]))
src = (sys.argv[3], int(sys.argv[4]))

FIN = 1
SYN = 2
ACK = 4

sock.bind(src)

msg = pack(">IIHH", int(sys.argv[5]), 0, int(sys.argv[6]), FIN)
sock.sendto(msg, dst)
