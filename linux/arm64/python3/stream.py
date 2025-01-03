#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys
import json, queue, struct, urllib.request, urllib.parse, logging, logging.handlers
import re
import threading
import hashlib
import time
import datetime
import base64
import socket
import hmac
import subprocess
import multiprocessing
import platform
from xml.dom import minidom

import acrcloud_stream_tool

def get_remote_config(config):
    try:
        page = 1
        items = []
        if 'token' in config and 'bucket_id' in config:
            access_token = config['token']
            bucket_id = config['bucket_id']

            http_uri = "/buckets/{}/channels".format(bucket_id)
            while True:
                requrl = "https://eu-api-v2.acrcloud.com/api" + http_uri + "?ingest=1&page="+str(page)
                if "stream_ids" in config and len(config['stream_ids']) > 0:
                    requrl = "https://eu-api-v2.acrcloud.com/api" + http_uri + "?type=ingest&page="+str(page)+"&streams="+",".join(str(x) for x in config['stream_ids'])
                req = urllib.request.Request(requrl)
                req.add_header("Authorization", "Bearer %s" % access_token)
                req.add_header("Accept", "application/json")
                response = urllib.request.urlopen(req)
                recv_msg = response.read()
                json_res = json.loads(recv_msg)
                logging.getLogger('acrcloud_stream').info(recv_msg)
                if len(json_res['data']) > 0:
                    for one in json_res['data']:
                        items.append(one)
                    if json_res['meta']['current_page'] >= json_res['meta']['last_page']:
                        break 
                    else:
                        page = page+1
                else:
                    break
        else:
            bucket_name = config['bucket_name']
            access_key = config['access_key']
            access_secret = config['access_secret']
            http_uri = "/v2/buckets/"+bucket_name+"/channels"
            while True:
                requrl = "https://api.acrcloud.com" + http_uri + "?type=ingest&page="+str(page)
                if "stream_ids" in config and len(config['stream_ids']) > 0:
                    requrl = "https://api.acrcloud.com" + http_uri + "?type=ingest&page="+str(page)+"&streams="+",".join(str(x) for x in config['stream_ids'])
                req = urllib.request.Request(requrl)
                base64string = base64.b64encode((('%s:%s' % (access_key, access_secret)).encode('ascii'))).decode('ascii')  
                req.add_header("Authorization", "Basic %s" % base64string)
                response = urllib.request.urlopen(req)
                recv_msg = response.read()
                json_res = json.loads(recv_msg)
                logging.getLogger('acrcloud_stream').info(recv_msg)
                if len(json_res['items']) > 0:
                    for one in json_res['items']:
                        items.append(one)
                    if json_res['_meta']['currentPage'] >= json_res['_meta']['pageCount']:
                        break 
                    else:
                        page = page+1
                else:
                    break
        return items
    except Exception as e:
        logging.getLogger('acrcloud_stream').error('get_remote_config : %s' % str(e))
        return []
    
class LiveStreamWorker():

    def __init__(self, stream_info, config):
        self._stream_info = stream_info
        self._config = config
        self._logger = logging.getLogger('acrcloud_stream')
        
    def start(self):
        try:
            work_queue = queue.Queue()
            decode_worker = self._DecodeStreamWorker(work_queue, self._stream_info, self._config)
            self._decode_worker = decode_worker
            decode_worker.start()
            process_worker = self._ProcessFingerprintWorker(work_queue, self._stream_info, self._config)
            self._process_worker = process_worker
            process_worker.start()
        except Exception as e:
            self._logger.error(str(e))

    def wait(self):
        try:
            self._decode_worker.join()
            self._process_worker.join()
        except Exception as e:
            self._logger.error(str(e))

    class _DecodeStreamWorker(threading.Thread):

        def __init__(self, worker_queue, stream_info, config):
            threading.Thread.__init__(self)
            self.setDaemon(True)
            self._config = config
            self._stream_url = stream_info['url']
            self._stream_url_list = []
            self._stream_acrid = stream_info['acr_id']
            self._program_id = stream_info.get('program_id', -1)
            self._worker_queue = worker_queue
            self._fp_interval = self._config.get('fp_interval_sec', 2)
            self._download_timeout = self._config.get('download_timeout_sec', 10)
            self._open_timeout = self._config.get('open_timeout_sec', 10)
            self._is_stop = True
            self._retry_n = 0 
            self._logger = logging.getLogger('acrcloud_stream')
            self._current_time = round(time.time())
            self._time_update_point = 0

        def run(self):
            self._is_stop = False
            self._logger.info(self._stream_acrid + " DecodeStreamWorker running!")
            self._check_url()
            self._logger.info(self._stream_url + ", after check_url:" + str(self._stream_url_list))
            while not self._is_stop:
                try:
                    for stream_url in self._stream_url_list:
                        self._decode_stream(stream_url)
                        time.sleep(1)
                        self._retry_n = self._retry_n + 1
                except Exception as e:
                    self._logger.error(str(e))
            self._logger.info(self._stream_acrid + " DecodeStreamWorker stopped!")

        def _decode_stream(self, stream_url):
            try:
                acrdict = {
                    'callback_func': self._decode_callback,
                    'stream_url': stream_url,
                    'read_size_sec':self._fp_interval,
                    'program_id':self._program_id,
                    'open_timeout_sec':self._open_timeout,
                    'read_timeout_sec':self._download_timeout,
                    'is_debug':0,
                }
                if (self._retry_n > 1 and stream_url[:4] == 'rtsp'):
                    acrdict['extra_opt'] = {'rtsp_transport':'tcp'}
                code, msg, ffcode, ffmsg = acrcloud_stream_tool.decode_audio(acrdict)
                #if code == 0:
                #    self._is_stop = True
                #else:
                self._logger.error("URL:"+str(stream_url) + ", CODE:"+str(code) + ", MSG:"+str(msg))
                self._logger.error("URL:"+str(stream_url) + ", FFCODE:"+str(ffcode) + ", FFMSG:"+str(ffmsg))
            except Exception as e:
                self._logger.error(str(e))

        def _decode_callback(self, res_data):
            try:
                if self._is_stop:
                    return 1
                if res_data.get('audio_data') != None:
                    # data_secs = round(float(len(res_data.get('audio_data')))/16000, 2)
                    # self._current_time = self._current_time + data_secs
                    # self._time_update_point = self._time_update_point + data_secs
                    # if self._time_update_point > 10:
                    #     self._current_time = round(time.time())
                    #     self._time_update_point = 0
                    now = datetime.datetime.now()
                    ts = datetime.datetime.timestamp(now)
                    self._current_time = round(ts)
                    task = (1, res_data.get('audio_data'), ts)
                    self._logger.info("audio len:" + str(len(res_data.get('audio_data'))))
                    self._worker_queue.put(task)
                else:
                    self._logger.info(str(res_data))
                return 0
            except Exception as e:
                self._logger.error(str(e))
        
        def _check_url(self):
            try:
                if self._stream_url.strip().startswith("mms://"):
                    slist = self._parse_mms(self._stream_url)
                    if slist:
                        self._stream_url_list = slist
                        return
                
                path = urllib.parse.urlparse(self._stream_url).path
                ext = os.path.splitext(path)[1]
                if ext == '.m3u':
                    slist = self._parse_m3u(self._stream_url)
                    if slist:
                        self._stream_url_list = slist
                elif ext == '.xspf':
                    slist = self._parse_xspf(self._stream_url)
                    if slist:
                        self._stream_url_list = slist
                elif ext == '.pls':
                    slist = self._parse_pls(self._stream_url)
                    if slist:
                        self._stream_url_list = slist
                else:
                    self._stream_url_list = [self._stream_url]
            except Exception as e:
                self._logger.error(str(e))

        def _parse_pls(self, url):
            plslist = []
            pageinfo = self._get_page(url)
            plslist = re.findall(r'(http.*[^\r\n\t ])', pageinfo)
            return plslist
            
        def _parse_m3u(self, url):
            m3ulist = []
            pageinfo = self._get_page(url)
            m3ulist = re.findall(r'(http.*[^\r\n\t "])', pageinfo)
            return m3ulist

        def _parse_xspf(self, url):
            #introduce: http://www.xspf.org/quickstart/
            xspflist = []
            pageinfo = self._get_page(url)
            xmldoc = minidom.parseString(pageinfo)
            tracklist = xmldoc.getElementsByTagName("track")
            for track in tracklist:
                loc = track.getElementsByTagName('location')[0]
                xspflist.append(loc.childNodes[0].data)
            return xspflist

        def _parse_mms(self, url):
            mmslist = []
            convert = ['mmsh', 'mmst', 'rtsp']
            mmslist = [ conv + url[3:] for conv in convert ]
            return mmslist

        def _get_page(self, url):
            resp = ''
            for i in range(2):
                req = urllib2.Request(url)
                try:
                    if url.startswith("https"):
                        context = ssl._create_unverified_context()
                        resp = urllib2.urlopen(req, context=context)
                    else:
                        resp = urllib2.urlopen(req)

                    if resp:
                        result = resp.read()
                        resp.close()
                        return result
                except Exception as e:
                    self._logger.error(str(e))
                    if resp:
                        resp.close()
            return ''
        
    class _ProcessFingerprintWorker(threading.Thread):

        def __init__(self, worker_queue, stream_info, config):
            threading.Thread.__init__(self)
            self.setDaemon(True)
            self._config = config
            self._worker_queue = worker_queue
            self._stream_info = stream_info
            self._fp_time = stream_info.get('fp_time_sec', 6)
            self._fp_max_time = stream_info.get('fp_max_time_sec', 12)
            self._fp_interval = stream_info.get('fp_interval_sec', 2)
            self._upload_timeout = stream_info.get('upload_timeout_sec', 10)
            self._record_upload_interval = stream_info.get('record_upload_interval', 60)
            self._record_fp_max_time = stream_info.get('record_fp_max_time', 120)
            self._is_stop = True
            self._logger = logging.getLogger('acrcloud_stream')

        def run(self):
            last_buf = b''
            record_last_buf = b''
            doc_pre_time = self._fp_time - self._fp_interval
            acr_id = self._stream_info['acr_id']
            self._logger.info(acr_id + " ProcessFingerprintWorker running!")
            self._is_stop = False
            timeshift = self._stream_info.get('timeshift', 0)
            while not self._is_stop:
                try:
                    live_upload = True
                    task = self._worker_queue.get()
                    task_type, now_buf, ts = task
                    if task_type == 2:
                        self._stream_info = now_buf 
                    cur_buf = last_buf + now_buf
                    last_buf = cur_buf

                    fp = acrcloud_stream_tool.create_fingerprint(cur_buf, False, 50, 0)
                    if fp and not self._upload_ts(fp, ts):
                        live_upload = False
                        if len(last_buf) > self._fp_max_time*16000:
                            last_buf = last_buf[len(last_buf)-self._fp_max_time*16000:]

                    if live_upload and len(last_buf) > doc_pre_time*16000:
                        last_buf = last_buf[-1*doc_pre_time*16000:]

                    if timeshift:
                        record_last_buf = record_last_buf + now_buf
                        if len(record_last_buf) > self._record_upload_interval * 16000:
                            record_fp = acrcloud_stream_tool.create_fingerprint(record_last_buf, False, 50, 0)
                            if record_fp and self._upload_record(record_fp, ts):
                                record_last_buf = b''
                            else:
                                if len(record_last_buf) > self._record_fp_max_time * 16000:
                                    record_last_buf = record_last_buf[len(last_buf)-self._record_fp_max_time*16000:]

                except Exception as e:
                    self._logger.error(str(e))
            self._logger.info(acr_id + " ProcessFingerprintWorker stopped!")

        def _upload_ts(self, fp, ts):
            result = True
            acr_id = self._stream_info['acr_id']
            stream_id = self._stream_info['id']
            timestamp = int(ts*1000)
            detail = str(stream_id)+":"+str(timestamp)
            try:
                host = self._stream_info['live_host']
                port = self._stream_info['live_port']
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._upload_timeout)
                sign = acr_id + (32-len(acr_id))*chr(0)
                body = sign.encode('ascii') +struct.pack('I', len(detail)) + detail.encode('ascii') + fp
                header = struct.pack('!cBBBIB', b'M', 1, 24, 0, len(body)+1, 2)
                sock.connect((host, int(port)))
                sock.sendall(header+body)
                row = struct.unpack('!ii', sock.recv(8))
                res_ret = sock.recv(row[1])
                self._logger.info(acr_id + ":record:" + str(len(fp)) + ":" + detail+":"+ res_ret.decode('ascii'))
                sock.close()
            except Exception as e:
                result = False
                self._logger.error(acr_id + ":record:" + str(len(fp)) + ":" + str(e))

            return result

        def _upload(self, fp):
            result = True
            acr_id = self._stream_info['acr_id']
            try:
                host = self._stream_info['live_host']
                port = self._stream_info['live_port']
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._upload_timeout)
                sign = acr_id + (32-len(acr_id))*chr(0)
                body = sign.encode('ascii') + fp
                header = struct.pack('!cBBBIB', b'M', 1, 24, 1, len(body)+1, 1)
                sock.connect((host, int(port)))
                sock.sendall(header + body)
                row = struct.unpack('!ii', sock.recv(8))
                res_ret = sock.recv(row[1])
                self._logger.info(acr_id + ":" + str(len(fp)) + ":" + res_ret.decode('ascii'))
                sock.close()
            except Exception as e:
                result = False
                self._logger.error(acr_id + ":" + str(len(fp)) + ":" + str(e))

            return result

        def _upload_record(self, fp, ts):
            result = True
            acr_id = self._stream_info['acr_id']
            stream_id = self._stream_info['id']
            timestamp = int(ts)
            detail = str(stream_id)+":"+str(timestamp)
            try:
                host = self._stream_info['timeshift_host']
                port = self._stream_info['timeshift_port']
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._upload_timeout)
                sign = acr_id + (32-len(acr_id))*chr(0)
                body = sign.encode('ascii') +struct.pack('I', len(detail)) + detail.encode('ascii') + fp
                header = struct.pack('!cBBBIB', b'M', 1, 24, 0, len(body)+1, 2)
                sock.connect((host, int(port)))
                sock.sendall(header+body)
                row = struct.unpack('!ii', sock.recv(8))
                res_ret = sock.recv(row[1])
                self._logger.info(acr_id + ":record:" + str(len(fp)) + ":" + detail+":"+ res_ret.decode('ascii'))
                sock.close()
            except Exception as e:
                result = False
                self._logger.error(acr_id + ":record:" + str(len(fp)) + ":" + str(e))

            return result

class LiveStreamManagerProcess(multiprocessing.Process):

    def __init__(self, streams, config):
        multiprocessing.Process.__init__(self)
        self.daemon = True
        self._streams = streams
        self._config = config
        self._workers = []
        self._logger = logging.getLogger('acrcloud_stream')

    def run(self):
        platform_s = platform.system()
        if platform_s and platform_s.lower().strip() != 'linux':
            if self._config.get('debug'):
                init_log(logging.INFO, self._config['log_file'])
            else:
                init_log(logging.ERROR, self._config['log_file'])
        self.run_worker()
        self.wait()

    def run_worker(self):
        try:
            for stream_t in self._streams:
                worker = LiveStreamWorker(stream_t, self._config)
                worker.start()
                self._workers.append(worker)
        except Exception as e:
            self._logger.error(str(e))

    def wait(self):
        try:
            for w in self._workers:
                w.wait()
        except Exception as e:
            self._logger.error(str(e))

class LiveStreamClient():

    def __init__(self, config):
        self._is_stop = True
        self._manager_process = []
        self._config = config
        self._logger = logging.getLogger('acrcloud_stream')

    def start_single(self):
        self._run_single()

    def start_withwatch(self):
        client_process = self._run_by_process()
        restart_interval = int(self._config.get('restart_interval_seconds', 0))
        check_update_interval = int(self._config.get('check_update_interval_minute', 0)) * 60

        watch_num = 0
        check_update_num = 0
        self._is_stop = False
        while not self._is_stop:
            try:
                if not self._check_alive():
                    self._check_update()
                    self._kill_process()
                    self._run_by_process()
                    watch_num = 0
                time.sleep(5)
                watch_num = watch_num + 5
                check_update_num = check_update_num + 5 
                if restart_interval > 0 and watch_num >= restart_interval:
                    self._check_update()
                    self._kill_process()
                    self._run_by_process()
                    watch_num = 0
                if check_update_interval > 0 and check_update_num > check_update_interval:
                    if self._check_update():
                        self._kill_process()
                        self._run_by_process()
                        check_update_num = 0
            except Exception as e:
                self._logger.error(str(e))

    def _check_update(self):
        try:
            streams = get_remote_config(self._config)
            update = False
            d = {}
            for s in self._config['streams']:
                d[s['id']] = s
            for s in streams:
                if s['id'] not in d:
                    update = True
                    self._config['streams'] = streams
                    break
                else:
                    if d[s['id']]['live_host'] != s['live_host'] or d[s['id']]['live_port'] != s['live_port'] \
                            or d[s['id']]['timeshift_host'] != s['timeshift_host'] or d[s['id']]['timeshift_port'] != s['timeshift_port'] \
                            or d[s['id']]['url'] != s['url'] or d[s['id']]['timeshift'] != s['timeshift']:
                        update = True
                        self._config['streams'] = streams
                        break
            print (update, streams)
            return update
        except Exception as e:
            self._logger.error(str(e))

    def _run_single(self):
        client_process = LiveStreamManagerProcess(self._config['streams'], self._config)
        client_process.run_worker()
        client_process.wait()
                 
    def _run_by_process(self):
        self._manager_process = []
        try:
            client_process = LiveStreamManagerProcess(self._config['streams'], self._config)
            client_process.start()
            self._manager_process.append(client_process)
        except Exception as e:
            self._logger.error(str(e))

    def _check_alive(self):
        res = True
        try:
            for mp in self._manager_process:
                if not mp.is_alive():
                    res = False
                    break
        except Exception as e:
            self._logger.error(str(e))
        return res


    def _kill_process(self):
        try:
            for mp in self._manager_process:
                mp.terminate()
                mp.join()
        except Exception as e:
            self._logger.error(str(e))

def init_log(logging_level, log_file):
    try:
        logger1 = logging.getLogger('acrcloud_stream')
        logger1.setLevel(logging_level)
        if log_file.strip():
            acrcloud_stream = logging.handlers.RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=1)
            acrcloud_stream.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)s- %(message)s'))
            acrcloud_stream.setLevel(logging_level)
            logger1.addHandler(acrcloud_stream)
        else:
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)s - %(message)s'))
            ch.setLevel(logging_level)
            logger1.addHandler(ch)
        return logger1
    except Exception as e:
        print(str(e))
        sys.exit(-1)

def _execfile(filepath):
    init_config = {}
    with open(filepath, 'rb') as file:
        exec(compile(file.read(), filepath, 'exec'), init_config)
    return init_config

def parse_config():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        confpath = sys.argv[1]
    else:
        confpath = './client.conf'

    config = {}
    try:
        init_config = {}
        init_config = _execfile(confpath)
        log_file = init_config.get('log_file', '')
        config['log_file'] = log_file
        config['debug'] = init_config.get('debug')
        if init_config.get('debug'):
            init_log(logging.INFO, log_file)
        else:
            init_log(logging.ERROR, log_file)

        if 'console_access_key' in init_config and 'console_access_secret' in init_config:
            config['access_key'] = init_config['console_access_key']
            config['access_secret'] = init_config['console_access_secret']
        elif 'console_access_token' in init_config:
            config['token'] = init_config['console_access_token']
        else:
            print("Error: Load ./client.conf failed. console_access_token not exists in client.conf")
            sys.exit(1)

        config['remote'] = init_config.get('remote')
        config['restart_interval_seconds'] = init_config.get('restart_interval_seconds', 0)
        config['check_update_interval_minute'] = init_config.get('check_update_interval_minute', 0)
        config['is_run_with_watchdog'] = init_config.get('is_run_with_watchdog', 0)
        config['upload_timeout_sec'] = init_config.get('upload_timeout_sec', 10)
        if 'bucket_name' in init_config:
            config['bucket_name'] = init_config.get('bucket_name')
        if 'bucket_id' in init_config:
            config['bucket_id'] = init_config.get('bucket_id')
        config['record_upload'] = init_config.get('record_upload')
        config['record_upload_interval'] = init_config.get('record_upload_interval')
        config['download_timeout_sec'] = init_config.get('download_timeout_sec', 10)
        config['open_timeout_sec'] = init_config.get('open_timeout_sec', 10)
        config['stream_ids'] = init_config.get('stream_ids', [])
        if init_config.get('remote', 1):
            for i in range(3):
                config['streams'] = get_remote_config(config)
                if config['streams']:
                    break
                print('Error: get_remote_config None')
        else:
            config['streams'] = []
            for stream_t in init_config['source']:
                tmp_stream_info = {'url':stream_t[0], 'acr_id':stream_t[1]}
                if len(stream_t) == 3:
                    tmp_stream_info['program_id'] = int(stream_t[2])
                tmp_stream_info['host'] = init_config['server']['host']
                tmp_stream_info['port'] = init_config['server']['port']
                config['streams'].append(tmp_stream_info)
    except Exception as e:
        print("Error: Load ./client.conf failed." + str(e))
        sys.exit(1)
    return config


def main():
    config = parse_config()
    client = LiveStreamClient(config)
    #if config.get("is_run_with_watchdog"):
    client.start_withwatch()
    #else:
    #    client.start_single()

if __name__ == '__main__':
    main()
