# Live Stream Client Python (version 2.7.X)

## Overview
  [ACRCloud](https://www.acrcloud.com/) provides cloud [Automatic Content Recognition](https://www.acrcloud.com/docs/introduction/automatic-content-recognition/) services for [Audio Fingerprinting](https://www.acrcloud.com/docs/introduction/audio-fingerprinting/) based applications such as **[Audio Recognition](https://www.acrcloud.com/music-recognition)** (supports music, video, ads for both online and offline), **[Broadcast Monitoring](https://www.acrcloud.com/broadcast-monitoring)**, **[Second Screen](https://www.acrcloud.com/second-screen-synchronization)**, **[Copyright Protection](https://www.acrcloud.com/copyright-protection-de-duplication)** and etc.<br>
  
## Preparations: 
1. Before using this tool, you must register on our platform and log into your dashboard.
2. Sign up now for a free 14 day trial: [http://console.acrcloud.com/signup](http://console.acrcloud.com/signup)
3. Create a “Live Channel” bucket and add the url of your streams into it.
4. Then, create a “Live Channel Detection” project and attach the bucket which contains your chosen stream urls.
5. Save the “access_key” and “access_secret” of the project which you have created.
 
## Configure
## client.conf
```python
   # You must replace "XXXXXX" with your access_key and access_secret.
   access_key = "XXXXXX"
   access_secret = "XXXXXX"
   remote = 1 
   debug = 0 
   
   # If you do not set log_file, the log will be echo to console.
   log_file = "acrcloud_stream.log"

   # If you set restart_interval_minute, the tool will restart every (restart_interval_minute) minutes.
   restart_interval_minute = 0 

   # If you set is_run_with_watchdog, there will be a daemon which is used to watch over streams process.
   is_run_with_watchdog = 1 
   
   server = { 
       'host': '',
       'port': 0,
   }
   
   source = [ 
   #       ['udp://127.0.0.1:1234', '(acrc id)', (program_id, default -1)],
   ] 
```

## Run The Tool
1. start
```python
   python stream.py 
   or
   nohup python stream.py &
```
2. stop
```python
   ps -ef | grep stream.py | grep -v grep | awk '{print $2}'| xargs kill -9
```
