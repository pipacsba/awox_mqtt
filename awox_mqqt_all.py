#!/usr/bin/python -u
# python script to handle awox lamp with json MQTT light
# JSON mapping
# {
#  "brightness": 255,       - WHITE_BRIGHTNESS
#  "color_temp": 155,       - COLOR_BRIGHTNESS
#  "color": {               - COLOR_CODE
#    "r": 255,
#    "g": 180,
#    "b": 200,
#  },
#  "state": "ON",           - NOT USED
#  "white_value": int       - WHITE_TEMPERATURE
#  "effect": "toggle"
# }
# remember: 
# - modified python module: python-awox-mesh-light-master
# - do not install bluepy from wheel (--use-no-wheel)
import paho.mqtt.client as mqtt
import awoxmeshlight
import time
import json
import signal
import subprocess

# Global Constants
MAX_RETRY = 1
MAX_CONNECT_TIME = 8  # [sec]
# reduced light brightness
NIGHT_BRIGHTNESS = 35
# full light brightness
FULL_BRIGHTNESS = 126
# White temperature for low light
WHITE_TEMPERATURE = 127
# White temperature for full light
WHITE_TEMPERATURE_FL = 64

# End Global Constants

# Global variables (save data over switches / MQTT messages)
# global White_Brightness
White_Brightness = 0
# global Color_Brightness
Color_Brightness = 0
# global Color_Red
Color_Red = 0
# global Color_Blue
Color_Blue = 0
#  global Color_Green
Color_Green = 0
# global White_Temperature
White_Temperature = 0
# input message
home_rgbw1_data = dict()
# message received flag
message_received = 0
# loops since last message
loops_since_last_message = 0
# define my_light
my_light = awoxmeshlight.AwoxMeshLight("XX:XX:XX:XX:XX:XX", "XXXXXXXX", "XXXXXXXX")
# my_light_connected
connected = 0
# last known state of the bulb
bulb_last_known_state = 0
# End Global parameters


# define handler to exit my_light.connect() after some defined time
def handler(signum, frame):
    # print "Forever is over!"
    raise Exception("end of time")


# state_topic: "home/rgbw1"
# command_topic: "home/rgbw1/set"
# The callback for when the client receives a CONNACK response from the server.
def on_connect(this_client, user_data, flags, rc):
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    this_client.subscribe("home/rgbw1/set", 1)


# The callback for when a PUBLISH message is received from the server.
def on_message(this_client, user_data, msg):
    # print(msg.topic + " " + str(msg.payload))
    global message_received
    message_received = 1
    global home_rgbw1_data
    home_rgbw1_data = msg.payload


# makes a structs from the binary message
def parse_result(message):
    # Format message ints into string of hex
    message = "".join("%02x" % b for b in message)
    # define result as empty dictionary
    result = dict()
    # save into the dictionary the original input from the lamp
    result['debug'] = message
    # read meshID
    mesh_id = int(message[6:8], 16)
    # read mode
    mode = int(message[24:26], 16)
    # filter some messages that return something else
    if mode < 40 and mesh_id == 0:
        # define status
        result['status'] = mode % 2
        # define mode
        result['mode'] = mode
        # read whiteTemperature value
        result['white_temperature'] = int(message[28:30], 16)  # convert to integer value
        # read whiteBrightness value
        result['white_brightness'] = int(message[26:28], 16)  # convert to integer value
        # read color code
        result['color'] = "#" + message[32:38]
        # read colorBrightness
        result['color_brightness'] = int(message[30:32], 16)  # convert to integer value
    if result['mode'] == 1 or mode == 6 or mode == 9:
        if result['white_brightness'] > 100:
            result['mode_string'] = "bright white"
        else:
            result['mode_string'] = "dark white"
    else:
        result['mode_string'] = "color"
    return result


# this function will connect to the bulb, and based on current status will change it's settings
def change_bulb_setting(json_msg):
    # print("change_bulb setting is called")
    # define bulb_respond
    bulb_resp = dict()
    # what to change:
    this_change_white = False
    this_change_color = False
    if connected == 1:
        # "brightness": 255,       - WHITE_BRIGHTNESS
        if "brightness" in json_msg:
            # global parameters to be updated here:
            global White_Brightness
            # print(int(json_msg["brightness"]))
            White_Brightness = int(int(json_msg["brightness"]) * 126 / 255)
            this_change_white = True
        # "color_temp": 155,       - COLOR_BRIGHTNESS
        if "color_temp" in json_msg:
            # global parameters to be updated here:
            global Color_Brightness
            Color_Brightness = int(int(json_msg["color_temp"]) * 100 / 500)
            this_change_color = True
        #  "color": {               - COLOR_CODE
        if "color" in json_msg:
            # global parameters to be updated here:
            global Color_Red
            global Color_Blue
            global Color_Green
            # read int values from message
            Color_Red = (int(json_msg["color"]["r"]))
            Color_Blue = (int(json_msg["color"]["b"]))
            Color_Green = (int(json_msg["color"]["g"]))
            # convert int values to hex without '0x' prefix
            this_change_color = True
            # print("red: " + str(Color_Red))
            # print("green: " + str(Color_Green))
            # print("blue: " + str(Color_Blue))
        #  "white_value": int       - WHITE_TEMPERATURE
        if "white_value" in json_msg:
            global White_Temperature
            White_Temperature = int(int(json_msg["white_value"]) * 127 / 255)
            this_change_white = True
        # print("W:" + str(this_change_white) + " C:" + str(this_change_color))
        if this_change_white:
            if White_Temperature != 0 and White_Brightness != 0:
                # send the message to the bulb
                my_light.setWhite(White_Temperature, White_Brightness)
        if this_change_color:
            if Color_Brightness != 0 and (Color_Red != 0 or Color_Blue != 0 or Color_Green != 0):
                my_light.setColor(Color_Red, Color_Green, Color_Blue)
                time.sleep(0)
                my_light.setColorBrightness(Color_Brightness)
        # sleep 1 second
        time.sleep(1)
        # read out the current settings
        my_light.readStatus()
        # make the respond readable
        bulb_resp = parse_result(my_light.message)
    # combine respond texts (respond + retry_cause)
    bulb_state = dict()
    if connected == 1:
        bulb_state["status"] = "ON"  # status
    else:
        bulb_state["status"] = "OFF"  # status
        bulb_state["r"] = 0
        bulb_state["g"] = 0
        bulb_state["b"] = 0
        bulb_state["color_temp"] = 0
        # as colored use, no white parameters
        bulb_state["brightness"] = 0
        bulb_state["white_value"] = 0
        bulb_state["effect"] = "OFF"
    if bulb_state["status"] == "ON":
        if bulb_resp["mode_string"] == "color":
            # global parameters to be updated here:
            # create hex() output
            red_string = "0x" + bulb_resp["color"][1] + bulb_resp["color"][2]
            green_string = "0x" + bulb_resp["color"][3] + bulb_resp["color"][4]
            blue_string = "0x" + bulb_resp["color"][5] + bulb_resp["color"][6]
            # transform to int
            Color_Red = int(red_string, 16)
            Color_Green = int(green_string, 16)
            Color_Blue = int(blue_string, 16)
            # assign state
            bulb_state["r"] = Color_Red
            bulb_state["g"] = Color_Green
            bulb_state["b"] = Color_Blue
            bulb_state["color_temp"] = bulb_resp["color_brightness"]  # COLOR_BRIGHTNESS
            # as colored use, no white parameters
            bulb_state["brightness"] = bulb_resp["white_brightness"]  # WHITE_BRIGHTNESS
            bulb_state["white_value"] = bulb_resp["white_temperature"]  # WHITE_TEMPERATURE
            bulb_state["effect"] = bulb_resp["mode_string"]
        else:
            # as white use, no color parameters
            bulb_state["r"] = Color_Red
            bulb_state["g"] = Color_Green
            bulb_state["b"] = Color_Blue
            bulb_state["color_temp"] = bulb_resp["color_brightness"]  # COLOR_BRIGHTNESS
            # assign state
            bulb_state["brightness"] = bulb_resp["white_brightness"]  # WHITE_BRIGHTNESS
            bulb_state["white_value"] = bulb_resp["white_temperature"]  # WHITE_TEMPERATURE
            bulb_state["effect"] = bulb_resp["mode_string"]
    # create output in JSON format
    change_bulb_respond = json.dumps({"state": bulb_state["status"],  # status
                                      "color_temp": int(bulb_state["color_temp"] * 500 / 100),  # COLOR_BRIGHTNESS
                                      "brightness": int(bulb_state["brightness"] * 255 / 126),  # WHITE_BRIGHTNESS
                                      "white_value": int(bulb_state["white_value"] * 255 / 127),  # WHITE_TEMPERATURE
                                      "effect": bulb_state["effect"],
                                      "color": {
                                         "r": bulb_state["r"],
                                         "g": bulb_state["g"],
                                         "b": bulb_state["b"]}},
                                     sort_keys=True, indent=4, separators=(',', ': '))
    # print(change_bulb_respond)
    # return the respond text
    return change_bulb_respond


client = mqtt.Client("awox_bulb")
client.on_connect = on_connect
client.on_message = on_message
signal.signal(signal.SIGALRM, handler)


client.connect("192.168.XX.XXX")

client.loop_start()

while True:
    # client.reconnect()
    # client.loop(0.1)
    if message_received == 1:
        message_received = 0
        loops_since_last_message = 0
        retries = 0
        this_msg = home_rgbw1_data.decode('utf-8')
        json_msg_in = json.loads(this_msg)
        if "effect" in json_msg_in and connected == 0:
            # print("effect requested")
            if "toggle" == json_msg_in["effect"]:
                print("Bluetooth reset called")
                subprocess.call(['sudo', '/usr/local/bin/restart_bluetooth'])
                time.sleep(2)
                retries = -1
        print(time.strftime('%a %H:%M:%S'), json_msg_in)
        while retries < MAX_RETRY and connected == 0:
            my_light = awoxmeshlight.AwoxMeshLight("XX:XX:XX:XX:XX:XX", "XXXXXXXX", "XXXXXXXX")
            # increase retry counter
            retries = retries + 1
            signal.alarm(MAX_CONNECT_TIME)
            try:
                my_light.connect()
            except Exception:
                pass
            else:
                connected = 1
            signal.alarm(0)
            if connected == 0:
                time.sleep(1)
                if bulb_last_known_state == 1:
                    print("Bluetooth reset called")
                    subprocess.call(['sudo', '/usr/local/bin/restart_bluetooth'])
                    time.sleep(2)
                if retries == MAX_RETRY:
                    print("BLE connection failed")
                    bulb_last_known_state = 0
            else:
                # signal.alarm(0)
                print("connected")
                bulb_last_known_state = 1
        if "effect" in json_msg_in and connected == 1:
            # print("effect requested")
            if "toggle" == json_msg_in["effect"]:
                # read out the current settings
                my_light.readStatus()
                # make the respond readable
                curr_stat = parse_result(my_light.message)
                # mode = 1; 9 means white mode
                if curr_stat['mode'] == 1 or curr_stat['mode'] == 9:
                    # if the current value is not the Night brightness
                    if abs(curr_stat['white_brightness'] - NIGHT_BRIGHTNESS) > 3:
                        # set to night mode
                        set_white_brightness = NIGHT_BRIGHTNESS
                        set_white_temp = WHITE_TEMPERATURE
                    # if the current value is the Night brightness
                    else:
                        # set to full brightness
                        set_white_brightness = FULL_BRIGHTNESS
                        set_white_temp = WHITE_TEMPERATURE_FL
                # if not white mode, than set the night mode whiteness
                else:
                    # set to night mode
                    set_white_brightness = NIGHT_BRIGHTNESS
                    set_white_temp = WHITE_TEMPERATURE
                this_msg = json.dumps({"state": "ON",  # status
                                       "brightness": int(set_white_brightness * 255 / 126),
                                       "white_value": int(set_white_temp * 255 / 127)},
                                      sort_keys=True, indent=4, separators=(',', ': '))
            elif "bright white" == json_msg_in["effect"]:
                # set to full brightness
                set_white_brightness = FULL_BRIGHTNESS
                set_white_temp = WHITE_TEMPERATURE_FL
                this_msg = json.dumps({"state": "ON",  # status
                                       "brightness": int(set_white_brightness * 255 / 126),
                                       "white_value": int(set_white_temp * 255 / 127)},
                                      sort_keys=True, indent=4, separators=(',', ': '))
            elif "dark white" == json_msg_in["effect"]:
                # set to night mode
                set_white_brightness = NIGHT_BRIGHTNESS
                set_white_temp = WHITE_TEMPERATURE
                this_msg = json.dumps({"state": "ON",  # status
                                       "brightness": int(set_white_brightness * 255 / 126),
                                       "white_value": int(set_white_temp * 255 / 127)},
                                      sort_keys=True, indent=4, separators=(',', ': '))
            else:
                this_msg = json.dumps({"state": "ON"},
                                      sort_keys=True, indent=4, separators=(',', ': '))
            print(this_msg)
            json_msg_in = json.loads(this_msg)
        status = change_bulb_setting(json_msg_in)
        # print(status)
        client.publish("home/rgbw1", status, 1, True)
    else:
        if loops_since_last_message < 33:
            loops_since_last_message += 1
        else:
            if connected == 1:
                my_light.disconnect()
                my_light = None
                print("disconnected")
                connected = 0
        # client.loop_stop()
        time.sleep(0.3)
        # client.reconnect()
        # client.loop_start()
