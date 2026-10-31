import subprocess,sys,resource,time
resource.setrlimit(resource.RLIMIT_CPU,(12,12))
code='import resource; resource.setrlimit(resource.RLIMIT_CPU,(6,6)); x=1\nwhile True: x=(x*17+3)%10000019'
children=[subprocess.Popen([sys.executable,'-c',code]) for _ in range(2)]
for child in children:child.wait()
print('UNEXPECTED_NORMAL_COMPLETION')
