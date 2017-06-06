#!/usr/bin/env python

import sqlite3
import subprocess
import os
import base64
import hashlib
import ConfigParser
import StringIO
import re
import itertools
import sys
import functools

def hashfile(afilename, hasher, blocksize=65536):
    with open(afilename, 'rb') as afile:
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
        return base64.b64encode(hasher.digest())
    
conn = sqlite3.connect('drivers.sqlite')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
hasher = hashlib.sha1()
os.chdir('extracted')

def find_pdb():
    proc = subprocess.Popen(['find', '.', '-name', '*.pdb'], stdout=subprocess.PIPE)
    for l in proc.stdout:
        fname = l.strip()
        bits = fname.split('/')
        
        if bits[0] == '.':
            bits = bits[1:]

        dirname = bits[0]
        path = '/'.join(bits[1:])
        
        subselect = "select download_digest from drivers where download_url like '%{}.cab' limit 1".format(dirname)
        filehash = hashfile(fname, hasher)
        print dirname, path, filehash
        cur.execute('insert into notable_files (download_digest, path, type, file_digest) values (('+subselect+'),?,?,?)', (path, 'pdb', filehash))
        conn.commit()
        
def find_services():
    proc = subprocess.Popen('find . -name "*.inf" | xargs -I{} grep -ali "ServiceType.*[12]0" "{}"', shell=True, stdout=subprocess.PIPE)
    for l in proc.stdout:
        fname = l.strip()
        bits = fname.split('/')
        
        if bits[0] == '.':
            bits = bits[1:]
        dirname = bits[0]
        path = '/'.join(bits[1:])
        print fname
        cur.execute("update drivers set has_userland_service=1 where download_url like '%{}.cab'".format(dirname))
        conn.commit()

        
def extract_devinst_details():
    proc = subprocess.Popen('find . -name "*.inf" | xargs -I{} grep -ali "\[Manufacturer\]" "{}"', shell=True, stdout=subprocess.PIPE)
    stdout, stderr  = proc.communicate()
    for l in stdout.split('\n'):
        fname = l.strip()
        bits = fname.split('/')
        
        if bits[0] == '.':
            bits = bits[1:]

        dirname = bits[0]
        path = '/'.join(bits[1:])
        print 'filename: %s' % fname
        hwids = find_usb_devname_from_inf(fname)
        if len(hwids) == 0:
            continue
        subselect = "select download_digest from drivers where download_url like '%{}.cab' limit 1".format(dirname)
        for h in hwids:
            cur.execute('insert into usb_ids (download_digest, dirname, inf_file, usbid) values(('+subselect+'),?,?,?)',
                (dirname, path, h))
            
 
        
        print path, hwids
        
    
def find_umdf_drivers():
    proc = subprocess.Popen('find . -name "*.inf" | xargs -I{} grep -ali "UmdfService" "{}"', shell=True, stdout=subprocess.PIPE)
    for l in proc.stdout:
        fname = l.strip()
        bits = fname.split('/')
        
        if bits[0] == '.':
            bits = bits[1:]

        dirname = bits[0]
        path = '/'.join(bits[1:])
        
        print fname
        try:
            binaries = find_umdf_binaries_from_inf(fname, dirname)
        except Exception as e:
            print "exception while processing %s" % fname
            print e
            continue
            
        subselect = "select download_digest from drivers where download_url like '%{}.cab' limit 1".format(dirname)
        print fname, binaries
        for b in binaries:
            hash = ''
            filesize = 0
            if b.startswith('/'): # file was actually found
                hash = hashfile((dirname + b), hasher)
                filesize = os.stat((dirname + b)).st_size
            
            cur.execute('insert into notable_files (download_digest, path, type, file_digest, file_size) values(('+subselect+'),?,?,?,?)',
                (b, 'umdf_driver', hash, filesize))
            
        cur.execute("update drivers set has_umdf_driver=1 where download_url like '%{}.cab'".format(dirname))
        conn.commit()
        
def find_all_coinstallers():
    proc = subprocess.Popen('find . -name "*.inf" | xargs -I{} grep -ali "CoInstallers32" "{}"', shell=True, stdout=subprocess.PIPE)
    for l in proc.stdout:
        fname = l.strip()
        bits = fname.split('/')
        
        if bits[0] == '.':
            bits = bits[1:]

        dirname = bits[0]
        path = '/'.join(bits[1:])
        coinstallers = find_coinstallers_in_inf(fname, dirname)
        for c in coinstallers:
            hash = ''
            filesize = 0
            if c.startswith('/'): # file was actually found
                hash = hashfile((dirname + c), hasher)
                filesize = os.stat((dirname + c)).st_size
            
            subselect = "select download_digest from drivers where download_url like '%{}.cab' limit 1".format(dirname)
            cur.execute('insert into notable_files (download_digest, path, type, file_digest, file_size) values(('+subselect+'),?,?,?,?)',
                (c, 'coinstaller', hash, filesize))
            conn.commit()
        print fname, coinstallers

        
def find_usb_devname_from_inf(inffile):
    if not os.path.exists(inffile):
        return []

    sio,other = preparse_inf(inffile)
    #print sio.read()
    try:
        p=ConfigParser.RawConfigParser()
        p.readfp(sio)
    except Exception as e:
        print "error in " + inffile
        print e
        return []
        
    hwsections = []
    for _,s in p.items('manufacturer'):
        bits = s.split(',')
        bits = [b.strip() for b in bits if len(b.strip()) > 0]
        prefix = bits.pop(0)
        if len(bits) == 0:
            hwsections.append(prefix)
        else:
            for b in bits:
                hwsections.append(prefix + '.' + b)
    hwids = set()
    for s in hwsections:
        try:
            items = p.items(s.lower())
        except:
            continue
        for _,i in items:
            devid = i.split(',').pop().strip()
            if devid.lower().startswith('usb\\') or devid.startswith('HID'):
                hwids.add(devid)
    return list(hwids)
    

        
def find_umdf_binaries_from_inf(inffile, dirname):
    sio,other = preparse_inf(inffile)
    try:
        p=ConfigParser.RawConfigParser()
        p.readfp(sio)
    except Exception as e:
        print "error in " + fname
        print e
        sys.exit(1)
        
    wdf_sections = [s for s in p.sections() if s.lower().endswith('.wdf')]
    binaries = []
    for s in wdf_sections:
        try:
            service = p.get(s, 'UmdfService')
        except:
            continue
        if service is None or ',' not in service:
            continue
        _,servicesection = service.split(',', 1)
        try:
            servicebinary = p.get(servicesection.strip(), 'ServiceBinary')
        except:
            continue
        if servicebinary is None:
            continue
        binary = os.path.basename(servicebinary.replace('\\', '/'))
        files = find_all_files(binary, dirname)
        if files:
            binary = files[0]
        binaries.append(binary)
    return binaries
    
def find_coinstallers_in_inf(fname, dirname):
    f,s=preparse_inf(fname)
    try:
        p=ConfigParser.RawConfigParser()
        p.readfp(f)
    except Exception as e:
        print "error in " + fname
        print e
        sys.exit(1)
        
    coinstlines = [l for l in itertools.chain(*s.values()) if 'coinstallers32' in l.lower()]
    coinstallers = []
    
    for l in coinstlines:
        try:
            l = repl_ini_vars(l, p)
        except Exception as e:
            print fname, e
            print
            print
        coinstallers += extract_coinstaller_details(l)
        
    coinstaller_files = []
    for c in coinstallers:
        name= c[0]
        files = find_all_files(name, dirname)
        if files:
            coinstaller_files.append(files[0])
        else:
            coinstaller_files.append(name)
    return coinstaller_files
    
def preparse_inf(fname):
    out = StringIO.StringIO()
    cont_line = False
    prev_line = None
    currentsection = ''
    sections = {}
    with open(fname, 'rU') as f:
        for line in f:
            parsedline = line.strip()
            if ';' in parsedline:
                parsedline = parsedline.split(';', 1)[0]
            
            if cont_line:         
                parsedline = prev_line + parsedline
                cont_line = False
            if parsedline.endswith("\\"):
                parsedline = parsedline.replace("\\", "")
                cont_line = True
                prev_line = parsedline
                continue
           
            if len(parsedline) == 0: # ignore blank lines
                continue
                
            if '=' not in parsedline:
                m = re.search('\[(.*)\]', line)
                if m is None:
                    s = sections.get(currentsection, [])
                    s.append(parsedline)
                    sections[currentsection] = s
                    continue
                else:
                    currentsection = m.group(1)
                    parsedline = '[' + m.group(1).strip().lower() + ']'
                    
            out.write(parsedline + "\n")
    out.seek(0, 0)   
    #for k,v in sections.iteritems():
    #    print k 
    #    for l in v:
    #        print "\t%s" % l
    return out, sections        

def do_repl(inifile, m):
    if inifile.has_section('Strings'):
        x = inifile.get('Strings', m.group(1))
    elif inifile.has_section('strings'):
        x = inifile.get('strings', m.group(1))
    else:
        x='???'
    x=x.replace('"','')
    return x
    
def repl_ini_vars(s, inifile):
    s = re.sub('%(.*?)%', functools.partial(do_repl, inifile), s)
    return s
    
def extract_coinstaller_details(l):
    #l = l.split(',', 4)[-1] # remove HKR,,CoInstallers32,0x00010000
    bits = re.findall('"(.*?)"', l)
    return [b.split(',', 1) for b in bits]
    
def find_all_files(name, path):
    result = []
    for root, dirs, files in os.walk(path):
        if name.lower() in map(str.lower, files):
            result.append(os.path.join(root, name))
        
    files = []
    for r in result:
        files.append(r.replace(path, ''))
    return files
    
extract_devinst_details()
find_pdb()
find_all_coinstallers()
find_umdf_drivers()
find_services()

#print find_umdf_binaries_from_inf('./5310_b2e6cc06628fb7793c976845b2c9d4297c75e436/SgFduWumdf.inf', '5310_b2e6cc06628fb7793c976845b2c9d4297c75e436')

#print find_usb_devname_from_inf('./20728412_96ab2a8cfc15d32e2295ec3663aadd46ac399288/net9500-x86-n630f.inf')

conn.commit()