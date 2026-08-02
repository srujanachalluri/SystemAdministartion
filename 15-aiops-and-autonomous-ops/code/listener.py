#!/usr/bin/env python3
"""Rep 8 fallback: the fake attacker endpoint, when netcat is not installed.

Does exactly what `nc -l 9999` does for this lab — listens on localhost, accepts
one connection, prints whatever arrives. Localhost only, never a real host.

  python code/listener.py &
"""

import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 9999))
    s.listen(1)
    print("[listener] waiting on 127.0.0.1:9999 ...", flush=True)
    conn, addr = s.accept()
    with conn:
        data = conn.recv(65535)
    print(f"[listener] ATTACKER RECEIVED from {addr[0]}:\n{data.decode(errors='replace')}",
          flush=True)
