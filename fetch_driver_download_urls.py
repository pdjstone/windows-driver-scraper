#!/usr/bin/env python

import requests
import sqlite3
import re
import os
from requests import Request, Session
import traceback
from multiprocessing import Pool, JoinableQueue

# TODO: stop this script from stalling before it has fetched all the download URLs

def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]
        
def get_download_request(guids):
    updateIDs = ['{"updateID":"%s"}' % guid for guid in guids]
    updateIDs = '[%s]' % ','.join(updateIDs)
    req = Request('POST', WU_DOWNLOAD_URL, params={'updateIDs':updateIDs}, headers={'user-agent': IE_USER_AGENT})
    return req.prepare()
   
def process_response(resp):
    results = re.findall('^downloadInformation\[(\d+)\].*(updateID|digest|url)\s*=\s*\'(.*)\'', resp.text, re.MULTILINE)
    driver_data = {}
    for result in results:
        id, key, value = result
        id = int(id)
        d = driver_data.get(id, {})
        d[key] = value
        driver_data[id] = d
        print key, value
    return driver_data
    
def update_db(driver_data):
    insert_data = [(d['url'], d['digest'], d['updateID']) for d in driver_data.values()]
    print 'adding %d urls to db' % len(insert_data)
    c = conn.cursor()
    c.executemany('update drivers set download_url=?, download_digest=? where guid=?', insert_data)
    conn.commit()
    
def request_worker(in_queue, out_queue):
    pid = os.getpid()
    sess = requests.Session()
    print 'worker %d' % pid
    while True:
        #if in_queue.empty():
        #    print '%d: queue empty, finishing' % pid
        #    break
        request = in_queue.get(True)
        try:
            response = sess.send(request)
            if response.status_code == 200:
                data = process_response(response)
                out_queue.put(data)
            else:
                raise Exception('status code %d for request %s' % (response.status_code, request.url))
        except Exception as e:
            traceback.print_exc()
        in_queue.task_done()

        
def get_guids_to_download():
    c = conn.cursor()
    guids = []
    c.execute('select usb_vid, guid, version from drivers where download_url is null group by usb_vid, version')
    for row in c:
        guids.append(row['guid'])
    return guids

WU_DOWNLOAD_URL = 'http://catalog.update.microsoft.com/v7/site/DownloadDialog.aspx'
IE_USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko'

conn = sqlite3.connect('drivers.sqlite')
conn.row_factory = sqlite3.Row

request_queue = JoinableQueue()
result_queue = JoinableQueue()

guids = get_guids_to_download()
grouped_guids = chunks(guids, 20)
[request_queue.put(get_download_request(g)) for g in grouped_guids]

pool = Pool(4, request_worker, (request_queue, result_queue))
pool.close()

while True:   
    try:
        driver_data = result_queue.get(True)
    except Exception as e:
        traceback.print_exc()
        break
 
    update_db(driver_data)



