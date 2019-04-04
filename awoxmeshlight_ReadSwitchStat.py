# -*- coding: utf-8 -*-
import json
import wiringpi

# wiringPI Defines
HIGH = 1
LOW = 0
MSBFIRST = 1
LSBFIRST = 0
WPI_MODE_PINS = 0
WPI_MODE_GPIO = 1
WPI_MODE_SYS = 2
MODE_PINS = 0
MODE_GPIO = 1
MODE_SYS = 2
INPUT = 0
OUTPUT = 1
PWM_OUTPUT = 2
PUD_OFF = 0
PUD_DOWN = 1
PUD_UP = 2

# initialise wiringPI module
wiringpi.wiringPiSetup()
if (wiringpi.getAlt(27) != 0):
    # set pin 27 as input
    wiringpi.pinMode(27, INPUT)
# else:
#     print("no pinmode changed")
# pull up pin 27
wiringpi.pullUpDnControl(27, PUD_UP)
# save initial switch status 
switch_state = wiringpi.digitalRead(27)
# remove pull-up (save current) [TODO: does it harm the PI to make so many switch?]
wiringpi.pullUpDnControl(27, PUD_OFF)

json_out = json.dumps({"switch_state": switch_state}, 
                      sort_keys=True, indent=4, separators=(',', ': '))
print(json_out)
