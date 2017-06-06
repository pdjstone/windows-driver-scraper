#!/usr/bin/env python
import sys
import os.path
import os
import subprocess

args = sys.argv[1:]

# run this as: python extract.py downloads/*.cab

SEVENZIP_PATH = '../7z/7za.exe'
SEVENZIP_PATH = '7za'

for f in args:
    path,e =  os.path.splitext(f)
    cabdirname = os.path.basename(path)
    extractpath = 'extracted/%s' % cabdirname
    print extractpath
    try:
        os.makedirs(path)
    except:
        pass
        
    subprocess.call([SEVENZIP_PATH, 'x', '-y', '-o'+extractpath, f, '*.inf', '*.pdb'])