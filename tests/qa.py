#!/usr/bin/env python
import subprocess
import signal

signal.signal(signal.SIGCHLD, signal.SIG_IGN)
print(subprocess.getoutput('/bin/ls -l'))

