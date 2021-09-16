#Push Tool Python (version 2.7.X)

## Preparations: 
1. Create ACRCloud account token.
![image](https://github.com/acrcloud/live_stream_client/blob/master/local_push_stream_tool/tutorial_image/create_account_token.png) <br>
2. Create local stream monitor project.
![image](https://github.com/acrcloud/live_stream_client/blob/master/local_push_stream_tool/tutorial_image/create_local_streams.png) <br>
3. Add local stream(raspberry-pi-3-model-b-plus).
![image](https://github.com/acrcloud/live_stream_client/blob/master/local_push_stream_tool/tutorial_image/raspberry-pi-3-model-b-plus_usb_url.png) <br>
![image](https://github.com/acrcloud/live_stream_client/blob/master/local_push_stream_tool/tutorial_image/add_streams.png) <br>
4. Modify the config file.
![image](https://github.com/acrcloud/live_stream_client/blob/master/local_push_stream_tool/tutorial_image/modify_config_file.png) <br>
 
## Run the push tool
1. install push tool
```
   apt install ffmpeg
```
2. start
```shell
  sh start.sh 
```
3. stop
```shell
  sh stop.sh
```
