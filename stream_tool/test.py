#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time
import json, Queue
import threading
import acrcloud_stream_decode

reload(sys)
sys.setdefaultencoding("utf8")

class DecodeStreamWorker(threading.Thread):

    def __init__(self, recognize_queue, stream_info):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self._stream_url = stream_info['url']
        self._recognize_queue = recognize_queue 
        self._fp_interval = 10
        self._download_timeout = 20
        self._is_stop = True

    def run(self):
        print "starting: " + self._stream_url
        self._is_stop = False
        while not self._is_stop:
            try:
                self._decode_stream(self._stream_url)
                time.sleep(1)
            except Exception as e:
                print e
        print "end: " + self._stream_url

    def _decode_stream(self, stream_url):
        try:
            acrdict = {
                'callback_func': self._decode_callback,
                'stream_url': stream_url,
                'read_size_sec':self._fp_interval,
                'open_timeout_sec':self._download_timeout,
                'read_timeout_sec':self._download_timeout,
                'is_debug':0,
            }
            code, msg, ff_code, ff_msg = acrcloud_stream_decode.decode_audio(acrdict)
            if code == 0:
                self._is_stop = True
            else:
                print stream_url + " CODE:"+str(code) + ", MSG:"+str(msg) + " " + str(ff_code) + " " + str(ff_msg)
        except Exception as e:
            print e

    def _decode_callback(self, res_data):
        try:
            if self._is_stop:
                return 1

            if res_data.get('metadata') != None:
                print res_data
            else:
                self._recognize_queue.put({'buf':res_data.get('audio_data'), 'url':self._stream_url})
            return 0
        except Exception as e:
            print e

if __name__ == '__main__':
    recognize_queue = Queue.Queue()
    workers = []

    # stream URL
    stream_info = {'url': ''}
    w = DecodeStreamWorker(recognize_queue, stream_info)
    workers.append(w)
    w.start()

    while True:
        try:
            now_item = recognize_queue.get()
            print now_item['url'], len(now_item['buf'])
        except Exception, e:
            print e
