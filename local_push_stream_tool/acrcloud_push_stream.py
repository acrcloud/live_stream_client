#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os, sys
import re
import json
import configparser
import hmac
import time 
import base64
import hashlib
import requests
import traceback
import subprocess
import signal
import logging, logging.handlers

if sys.version_info.major == 2:
    reload(sys)
    sys.setdefaultencoding("utf8")
else:
    import importlib
    importlib.reload(sys)

class StreamPushClient():

    def __init__(self, config):
        self._config = config
        self._logger = config['logger']
        self._push_process_map = {}

    def run(self):
        try:
            while True:
                self._check_active()
                time.sleep(self._config['config']['system']['check_interval'])
                self._logger.info('waiting... ' + str(time.time()) + ', streams=' + str(len(self._push_process_map)))
        #except KeyboardInterrupt:
        #    self.destroy()
        #    self._logger.error("push tool destroy")
        except Exception as e :
            self.destroy()
            self._logger.error("push tool destroy")

    def _check_active(self):
        try:
            streams = self._get_remote_info()
            streams_id_map = {}
            for stream_info in streams:
                stream_id = stream_info['id']
                streams_id_map[stream_id] = 1
                push_process_info = self._push_process_map.get(stream_id)
                
                if push_process_info:
                    old_stream_info = push_process_info['stream_info']
                    if self._check_same(old_stream_info, stream_info):
                        continue
                    else:
                        self._logger.warning("stream info changed...")
                        self._kill_all_process(push_process_info['proc'])

                proc = self._push(stream_info)
                if proc:
                    process_info = {
                        'stream_info': stream_info,
                        'proc': proc
                    }
                    self._push_process_map[stream_id] = process_info
                    self._logger.debug('push suss! ' + json.dumps(stream_info))

            new_push_process_map = {}
            for pk, pv in self._push_process_map.items():
                if not streams_id_map.get(pk):
                    self._kill_all_process(pv['proc'])
                    self._logger.warning("delete stream " + json.dumps(pv['stream_info']))
                    continue

                if pv['proc'].poll() != None:
                    self._kill_all_process(pv['proc'])
                    pv['proc'] = self._push(pv['stream_info'])
                new_push_process_map[pk] = pv
            self._push_process_map = new_push_process_map
        except Exception as e:
            self._logger.error(traceback.format_exc(e))

    def _check_same(self, stream_info1, stream_info2):
        try:
            if stream_info1['url'] == stream_info2['url'] \
                and stream_info1['user_defined']['type'] == stream_info2['user_defined']['type'] \
                and stream_info1['user_defined']['push_server'] == stream_info2['user_defined']['push_server']:

                return True
        except Exception as e:
            self._logger.error(traceback.format_exc(e))
        return False

    def _push(self, stream_info):
        try:
            if 'push_server' not in stream_info['user_defined']:
                self._logger.error('no push_server: ' + json.dumps(stream_info))
                return None
            push_server = stream_info['user_defined']['push_server']
            config_info = self._config['config']
            push_tool = config_info['system']['push_tool']
            stream_url = stream_info['url'].strip()
            is_device = False
            if stream_url.startswith('plughw'):
                is_device = True
                ss = stream_url.find('?')
                if ss > 0:
                    stream_url = stream_url[:ss]
            #cmd = [push_tool, '-loglevel', 'quiet', '-re', '-i', stream_url, '-c:a', 'aac']
            cmd = [push_tool, '-loglevel', 'quiet', '-re']
            if is_device:
                cmd += ['-f', 'alsa']
            cmd += ['-i', stream_url, '-c:a', 'aac']
            params_keys = [['-ar', 'sample_rate'], ['-ac', 'channels'], ['-b:a', 'bitrate']]
            for pk in params_keys:
                if config_info['audio'][pk[1]]:
                    cmd.append(pk[0])
                    cmd.append(str(config_info['audio'][pk[1]]))
            if 'type' in stream_info['user_defined'] and stream_info['user_defined']['type'] == 'video':
                params_keys = [['-s', 'scale'], ['-r', 'fps'], ['-b:v', 'bitrate']]
                if config_info['video'][pk[1]]:
                    cmd.append(pk[0])
                    cmd.append(str(config_info['video'][pk[1]]))

            metadata_keys = {
                'Server': 'ACRCloud',
                'id': str(stream_info['id']),
                'name': stream_info['stream_name'],
                'region': stream_info['region'],
                'url': stream_info['url'],
                'user_defined': json.dumps(stream_info['user_defined'])
            }
            for mk,mv in metadata_keys.items():
                cmd.append('-metadata')
                cmd.append(mk + '=' + str(mv))

            push_url = 'rtmp://' + push_server + '/live/' + str(stream_info['id'])
            cmd = cmd + ['-strict', '-2', '-f', 'flv', push_url]

            self._logger.debug(' '.join(cmd))

            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, 
                    stdout=subprocess.PIPE, preexec_fn=os.setsid, close_fds=True)

            self._logger.debug(' '.join(cmd) + "...... pid=" + str(proc))

            return proc
        except Exception as e:
            self._logger.error(traceback.format_exc(e))

    def destroy(self):
        self._logger.debug("destroy...")
        for pk, pv in self._push_process_map.items():
            self._kill_all_process(pv['proc'])
        sys.exit(1)

    def _kill_all_process(self, proc):
        if not proc:
            return

        try:
            proc.kill()
            proc.terminate()
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            proc.wait()
        except Exception as e:
            self._logger.error(traceback.format_exc(e))

    def _get_remote_info(self):
        streams = []
        try:
            self._logger.info("read remote stream info.")

            surl = self._config['config']['api']['url']
            account_access_key = str(self._config['config']['api']['account_access_key'])
            account_access_secret = str(self._config['config']['api']['account_access_secret'])
            project_name = self._config['config']['api']['project_name']
            stream_ids = self._config['config']['api']['stream_ids']
            if stream_ids:
                stream_ids = stream_ids.split(',')
            http_method = 'GET'
            http_uri = surl[surl.find("/v1/"):]
            signature_version = '1'

            timestamp = time.time()
            string_to_sign = "\n".join([http_method, http_uri, 
                account_access_key, signature_version, str(timestamp)])

            if sys.version_info.major == 2:
                sign = base64.b64encode(
                    hmac.new(
                        account_access_secret,
                        string_to_sign,
                        digestmod=hashlib.sha1).digest())
            else:
                sign = base64.b64encode(
                    hmac.new(
                        account_access_secret.encode('ascii'),
                        string_to_sign.encode('ascii'),
                        digestmod=hashlib.sha1).digest())

            headers = {
                "access-key": account_access_key,
                "signature-version": signature_version,
                "signature": sign,
                "timestamp": str(timestamp)
            }

            page = 1
            while True:
                s_info_h = requests.get(surl, params={'project_name': project_name, 'page': page}, 
                        headers=headers, verify=True)
                s_info = s_info_h.text
                self._logger.debug(s_info)
                json_res = json.loads(s_info)
                if len(json_res['items']) > 0:
                    for one in json_res['items']:
                        if stream_ids and one['id'] not in stream_ids:
                            continue
                        streams.append(one)
                    if json_res['_meta']['currentPage'] >= json_res['_meta']['pageCount']:
                        break
                    else:
                        page = page+1
                else:
                    break
        except Exception as e:
            self._logger.error(traceback.format_exc(e))
        return streams 

def init_log(config):
    try:
        logger = logging.getLogger("push_rtmp")
        logger_level_map = {'debug':logging.DEBUG, 'info':logging.INFO, 
                'warning':logging.WARNING, 'error':logging.ERROR}
        logger.setLevel(logger_level_map[config['log']['level']])
        if config['log']['file']:
            log_file_handler = logging.handlers.RotatingFileHandler(
                    config['log']['file'], maxBytes=config['log']['max_size'], backupCount=1)
            log_file_handler.setFormatter(
                    logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'))
            logger.addHandler(log_file_handler)

        if config['log']['console']:
            ch = logging.StreamHandler()
            ch.setFormatter(
                    logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'))
            logger.addHandler(ch)
        return logger
    except Exception as e:
        print(traceback.format_exc(e))
        sys.exit(-1)

def parse_config():
    try:
        if not os.path.exists("config.ini"):
            print("config.ini is not exitsts.")
            sys.exit()

        cf = configparser.ConfigParser()
        cf.read('config.ini')

        config = {
                'api':{
                    'url': 'https://api.acrcloud.com/v1/monitor-streams'
                }, 
                'log':{
                    'level': 'debug',
                    'console': True,
                    'file': 'push_stream_acrcloud.log',
                    'max_size': 10*1024*1024
                }, 
                'audio':{
                    'sample_rate': '8000',
                    'channels': '1',
                    'bitrate': ''
                }, 
                'video':{
                    'scale': '250x160',
                    'fps': '8',
                    'bitrate': '50k'
                },
                'system': {
                    'push_tool': 'ffmpeg',
                    'check_interval': 60
                }
            }

        config['api']['account_access_key'] = cf.get('api', 'account_access_key')
        if not config['api']['account_access_key']:
            print("account_access_key missing.")
            sys.exit(1)
        config['api']['account_access_secret'] = cf.get('api', 'account_access_secret')
        config['api']['url'] = cf.get('api', 'url')
        config['api']['project_name'] = cf.get('api', 'project_name')
        config['api']['stream_ids'] = cf.get('api', 'stream_ids')

        config['log']['level'] = cf.get('log', 'level')
        if config['log']['level']:
            config['log']['level'] = 'debug'
        config['log']['console'] = cf.getboolean('log', 'console')
        config['log']['file'] = cf.get('log', 'file')
        config['log']['max_size'] = cf.get('log', 'max_size')
        if 'max_size' in config['log']:
            config['log']['max_size'] = eval(config['log']['max_size'])
            if not config['log']['max_size']:
                config['log']['max_size'] = 10 * 1024 * 1024

        audio_keys = ['sample_rate', 'channels', 'bitrate']
        for ak in audio_keys:
            if ak in cf['audio']:
                config['audio'][ak] = cf.get('audio', ak)

        video_keys = ['scale', 'fps', 'bitrate']
        for vk in video_keys:
            if vk in cf['video']:
                config['video'][vk] = cf.get('video', vk)

        if 'push_tool' in cf['system']:
            config['system']['push_tool'] = cf.get('system', 'push_tool')
        if 'check_interval' in cf['system'] and cf['system']['check_interval']:
            config['system']['check_interval'] = int(cf['system']['check_interval'])

        return config
    except Exception as e:
        print(traceback.format_exc(e))

def main():
    print("parse config")
    config = parse_config()
    print(config)

    print("init log")
    logger = init_log(config)

    g_config = {'logger':logger, 'config':config}
    client = StreamPushClient(g_config)

    signal.signal(signal.SIGINT, client.destroy)
    signal.signal(signal.SIGHUP, client.destroy)
    signal.signal(signal.SIGTERM, client.destroy)
    signal.signal(signal.SIGQUIT, client.destroy)

    client.run()

if __name__ == '__main__':
    main()
