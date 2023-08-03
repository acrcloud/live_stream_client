#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time
import json, queue
import threading
import acrcloud_stream_tool

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
        print("starting: " + self._stream_url)
        self._is_stop = False
        while not self._is_stop:
            try:
                self._decode_stream(self._stream_url)
                time.sleep(1)
            except Exception as e:
                print(e)
        print("end: " + self._stream_url)

    def _decode_stream(self, stream_url):
        try:
            acrdict = {
                'callback_func': self._decode_callback,
                'stream_url': stream_url,
                'read_size_sec':self._fp_interval,
                'open_timeout_sec':self._download_timeout,
                'read_timeout_sec':self._download_timeout,
                'is_debug':0,
                #'out_channels': 1,
                #'out_sample_rate': 8000,
                #'is_return_video': 1,
                #'out_video_fps': 8,
                #'out_video_bitrate': 50000,
                #'out_video_width': 250,
                #'threads': 1,
            }
            code, msg, ff_code, ff_msg = acrcloud_stream_tool.decode_audio(acrdict)
            if code == 0:
                self._is_stop = True
            else:
                print(stream_url + " CODE:"+str(code) + ", MSG:"+str(msg) + " " + str(ff_code) + " " + str(ff_msg))
        except Exception as e:
            print(e)

    def _decode_callback(self, res_data):
        try:
            if self._is_stop:
                return 1

            if res_data.get('metadata') != None:
                print(res_data)
            else:
                self._recognize_queue.put({'abuf':res_data.get('audio_data'), 'vbuf':res_data.get('video_data'), 'url':self._stream_url})
            return 0
        except Exception as e:
            print(e)

def enc(pcm_buffer, atype='aac', is_strip=False):
    opt = {
        'sample_rate': 8000,
        'channels': 1,
        'bit_rate': 16*1024,
        'type': atype
    }
    if is_strip:
        opt['is_strip'] = 1
    encoder = acrcloud_stream_tool.Encoder(opt)
    encoder.write(pcm_buffer)
    abuf = encoder.read_all()
    return abuf

def get_enc_block_size(atype='aac'):
    opt = {
        'sample_rate': 8000,
        'channels': 1,
        'bit_rate': 16*1024,
        'is_strip': 1,
        'type': atype
    }
    encoder = acrcloud_stream_tool.Encoder(opt)
    return encoder.get_frame_size() * 2

def mix_list(list_files):
    muxer = acrcloud_stream_tool.Muxer()

    block_size = get_enc_block_size()
    last_buf = '\0'*block_size
    for pcm_file,h264_file in list_files:
        pcm_buffer_now = open(pcm_file, 'rb').read()
        pcm_buffer_a = last_buf + pcm_buffer_now
        ss = len(pcm_buffer_a) // block_size
        pcm_buffer = pcm_buffer_a[:ss*block_size]
        last_buf = pcm_buffer_a[(ss-1)*block_size:]
        aacbuf = enc(pcm_buffer, 'aac', True)
        h264buf = open(h264_file, 'rb').read()
        muxer.write(aacbuf, h264buf)
    mp4buf = muxer.read_all()
    out = open(list_file+ ".mp4", 'wb')
    out.write(mp4buf)
    out.close()

def mix(abuf, vbuf):
    muxer = acrcloud_stream_tool.Muxer()
    muxer.write(abuf, vbuf)
    return muxer.read_all()

def resample(src_buf, src_rate, dst_rate):
    dst_buf = acrcloud_stream_tool.resample(src_buf, src_rate, dst_rate)
    return dst_buf

if __name__ == '__main__':
    recognize_queue = queue.Queue()
    workers = []

    # stream URL
    stream_info = {'url': ''}
    w = DecodeStreamWorker(recognize_queue, stream_info)
    workers.append(w)
    w.start()

    while True:
        try:
            now_item = recognize_queue.get()
            print(now_item['url'], len(now_item['buf']))
        except Exception as e:
            print(e)
