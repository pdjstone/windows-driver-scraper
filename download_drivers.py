#!/usr/bin/env python

import requests
import sqlite3
import re
import os
from requests import Request, Session
from multiprocessing import Pool, JoinableQueue
import traceback
   

    
def update_db(driver_data):
    insert_data = [(d['url'], d['digest'], d['updateID']) for d in driver_data.values()]
    print 'adding %d urls to db' % len(insert_data)
    c = conn.cursor()
    c.executemany('update drivers set download_url=?, download_digest=? where guid=?', insert_data)
    conn.commit()
    
def download_url_to_file(url, dest_dir, sess):
    local_filename = url.split('/')[-1]
    local_path = os.path.join(dest_dir, local_filename)
    if os.path.exists(local_path):
        print 'file %s already exists, skipping' % local_filename
        return False
    response = sess.get(url, stream = True)
    if response.status_code != 200:
        print 'got status %d for %s' % (response.status_code, url)
        response.close()
        return False
    print 'starting %s' % url
    with open(local_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size = 1024):
            if chunk:
                f.write(chunk)
    print 'done'
    response.close()
    return True
 

def download_worker(in_queue):
    pid = os.getpid()
    sess = requests.Session()
    print 'worker %d' % pid
    while True:
        if in_queue.empty():
            print '%d: queue empty, finishing' % pid
            break
        url = in_queue.get(True)
        try:
            result = download_url_to_file(url, 'downloads', sess)
        except Exception as e:
            traceback.print_exc()
        in_queue.task_done()

        

url_queue = JoinableQueue()

conn = sqlite3.connect('drivers.sqlite')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('select distinct download_url from drivers where download_url is not null group by usb_vid, version')
for row in c:
    url_queue.put(row['download_url'])
    
print 'main proc %s' % os.getpid()
pool = Pool(6, download_worker, (url_queue,))
pool.close()
pool.join()



