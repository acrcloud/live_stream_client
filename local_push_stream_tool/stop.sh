ps -ef | grep acrcloud_push_stream.py| grep -v grep | awk '{print $2}'| xargs kill -9
ps -ef | grep ACRCloud | grep ffmpeg | grep -v grep | awk '{print $2}'| xargs kill -9
