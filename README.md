# Live Stream Client Python (version 2.7.X)

## Overview
  [ACRCloud](https://www.acrcloud.com/) provides services such as **[Music Recognition](https://www.acrcloud.com/music-recognition)**, **[Broadcast Monitoring](https://www.acrcloud.com/broadcast-monitoring/)**, **[Custom Audio Recognition](https://www.acrcloud.com/second-screen-synchronization%e2%80%8b/)**, **[Copyright Compliance & Data Deduplication](https://www.acrcloud.com/copyright-compliance-data-deduplication/)**, **[Live Channel Detection](https://www.acrcloud.com/live-channel-detection/)**, and **[Offline Recognition](https://www.acrcloud.com/offline-recognition/)** etc.<br>

## Windows Runtime Library 
**If you run the SDK on Windows, you must install this library.**<br>
X86: [download and install Library(windows/vcredist_x86.exe)](https://www.microsoft.com/en-us/download/details.aspx?id=5555)<br>
x64: [download and install Library(windows/vcredist_x64.exe)](https://www.microsoft.com/en-us/download/details.aspx?id=14632)

## Preparations: 
1. Before using this tool, you must register on our platform and log into your dashboard.
2. Sign up now for a free 14 day trial: [http://console.acrcloud.com/signup](http://console.acrcloud.com/signup)
3. Create a “Live Channel” bucket and add the url of your streams into it.
4. Create a console access key pairs in the account settings and input this key piars to your client.conf file
5. Input your Live Bucket Name to the client.conf file.
6. Run the stream.py
7. Create a “Live Channel Detection” project and attach the bucket which contains your chosen stream urls.
8. Then you can use our SDK to detect the current stream.
 
## Configure
## client.conf
```python
# -*- coding: utf-8 -*-
# You must replace "XXXXXX" with your console access token.
# Note: You can get it from the account setting
console_access_token = "XXXXXX"
bucket_id = YOUR_BUCKET_ID
#stream_ids = [""]
remote = 1
debug = 0

# If you do not set log_file, the log will be echo to console.
log_file = "acrcloud_stream.log"

# If you set restart_interval_seconds, the tool will restart every (restart_interval_seconds) seconds.
restart_interval_seconds = 0

#the tool will check whether the streams have been updated every check_update_interval_minute minutes
check_update_interval_minute = 60
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
