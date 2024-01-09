import fcntl
import os
import select
import socket
import logging
import struct
import sys
import termios
import atexit
import signal
import tty

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def pack_wndsize(w: int, h: int) -> bytes:
    """
    Send window size.
    """
    return struct.pack("!BHH", 0x1, w, h)


def pack_data(data: bytes) -> bytes:
    """
    Send data with the given operation.
    """
    return struct.pack("!BI", 0x0, len(data)) + data


def setupTerm():
    mode = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin)
    atexit.register(lambda: termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, mode))


def readInput():
    chs = b""
    ch = os.read(sys.stdin.fileno(), 1)
    while len(ch) > 0:
        chs += ch
        ch = os.read(sys.stdin.fileno(), 1)
    return chs


def main():
    if len(sys.argv) != 2:
        print("Usage: %s <port>" % sys.argv[0])
        sys.exit(1)

    port = int(sys.argv[1])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        logging.info("Listening on 0.0.0.0:%d", port)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.listen(1)

        conn, addr = sock.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        conn.setblocking(False)
        logging.info("Accept a connection from %s", addr)

    logging.info("Become a shell")
    setupTerm()

    orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)

    # handle SIGWINCH
    def sigwinch_handler(signum, frame):
        w, h = os.get_terminal_size()
        conn.sendall(pack_wndsize(w, h))

    sigwinch_handler(None, None)
    signal.signal(signal.SIGWINCH, sigwinch_handler)

    # copy bidirectionally between the socket and the terminal
    # using select() to multiplex
    while True:
        # wait for data to read
        r, _, x = select.select([conn, sys.stdin], [], [conn, sys.stdin])
        if conn in r:
            # read from socket and write to stdout
            data = conn.recv(1024)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        if sys.stdin in r:
            # read from stdin and write to socket
            data = sys.stdin.buffer.read()
            if not data:
                break
            conn.sendall(pack_data(data))
        if conn in x or sys.stdin in x:
            break

    logging.info("Connection closed")


if __name__ == "__main__":
    main()
