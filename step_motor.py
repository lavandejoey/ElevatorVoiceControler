import time, os, sys, json, threading, base64
from urllib.parse import urlencode, quote
from websocket import create_connection
from email.utils import formatdate
from threading import Lock, Thread
from hashlib import sha1
import RPi.GPIO as gpio
from socket import *
from array import *
import websocket
import hashlib
import logging
import hmac
import ssl

# delete when use in RPi:
#BOARD = 1

# rasp_pin:
vertical_PUL0 = 40  # GPIO21
vertical_PUL1 = 38  # GPIO10
vertical_DIR0 = 36  # GPIO16
vertical_DIR1 = 32  # GPIO19
horizon_PUL0 = 31  # GPIO22
horizon_PUL1 = 33  # GPIO23
horizon_DIR0 = 35  # GPIO24
horizon_DIR1 = 37  # GPIO25
# FAN = [4, 6]
innner_ele_mag = 37
upstair_ele_mag = 
downstair_ele_mag = 
vertical_reset_switch = 
horizon_reset_switch = 
gpio.setwarnings(False)
gpio.setmode(gpio.BOARD)
vertical_motor_ports = [vertical_PUL0, vertical_PUL1, vertical_DIR0, vertical_DIR1]  # the pins of step motor driver
# GPIO21 PUL+ (Pin 40), GPIO10 PUL- (Pin 38)
# GPIO16 DIR+ (Pin 36), GPIO19 DIR- (Pin 35)
horizon_motor_ports = [horizon_PUL0, horizon_PUL1, horizon_DIR0, horizon_DIR1]
for pm in (vertical_motor_ports + horizon_motor_ports):
    gpio.setup(pm, gpio.OUT)  # set step motor driver pin mode
ele_port = [innner_ele_mag, upstair_ele_mag, downstair_ele_mag]
for pe in ele_port:
    gpio.setup(pe, gpio.OUT)  # GPIO ELE_MAG 26 (Pin 37)
gpio.setup(vertical_reset_switch, gpio.IN, pull_up_down=gpio.PUD_DOWN)
gpio.setup(horizon_reset_switch, gpio.IN, pull_up_down=gpio.PUD_DOWN)

# init_creat_data:
target_floors = []  # set of target floor collection from voice recognitions
pressing_target = [0, 0]
# floor_num_trans
floor_position = [[0, 0], [31,-118.5], [31,-79], [31,-39.5],[31,0], [101.5,-79], [101.5,-79], [101.5,-39.5], [101.5,0]]  # original position and floors' (mm)
current_position = []
target_position = []
horizonal_step = 0
vertical_step = 0
v_flag = 0
h_flag = 0

# motor_init:
# global pos_dir, neg_dir
pos_dir = [3, 2, 1, 0]
neg_dir = [0, 1, 2, 3]


class StepMotor:
    def __init__(self):
        th_vertical_reset = Thread(target=StepMotor.vertical_motor_reset, daemon=True)
        th_horizon_reset = Thread(target=StepMotor.horizon_motor_reset, daemon=True)
        th_vertical_reset.start()
        th_horizon_reset.start()
        while not h_flag & v_flag:
            continue
        global current_position
        current_position = floor_position[0]
        print("Step-motor initialized!")

    def set_motor_step(mode1, mode2, mode3, mode4, port):
        modes = [mode1, mode2, mode3, mode4]
        i = 0
        for pin in port:
            gpio.output(pin, modes[i])
            i += 1

    def stop_motor(port):
        set_motor_step(0, 0, 0, 0, port)

    def backward_motor(delay, steps, port):
        for i in range(0, steps):
            set_motor_step(1, 0, 1, 0, port)
            time.sleep(delay)
            set_motor_step(0, 1, 1, 0, port)
            time.sleep(delay)
            set_motor_step(0, 1, 0, 1, port)
            time.sleep(delay)
            set_motor_step(1, 0, 0, 1, port)
            time.sleep(delay)

    def forward_motor(delay, steps, port):
        for i in range(0, steps):
            set_motor_step(1, 0, 0, 1, port)
            time.sleep(delay)
            set_motor_step(0, 1, 0, 1, port)
            time.sleep(delay)
            set_motor_step(0, 1, 1, 0, port)
            time.sleep(delay)
            set_motor_step(1, 0, 1, 0, port)
            time.sleep(delay)

    def ele_mag_act(self, mode=0):
        activated_ele_mag = ele_port[mode]
        try:
            gpio.output(activated_ele_mag, True)
            time.sleep(0.8)
            gpio.output(activated_ele_mag, False)
            return 1
        except BlockingIOError:
            return 0

    def horizon_motor_reset():  # horizonal motor position reset
        global h_flag
        while not gpio.input(horizon_reset_switch):
            # backward_motor(delay=0.00003, steps=5, port=horizon_motor_ports)
            forward_motor(delay=0.00003, steps=5, port=horizon_motor_ports)
        h_flag = 1
        print("horizotal reset complete!")

    def vertical_motor_reset():  # vertical motor position
        global v_flag
        while not gpio.input(vertical_reset_switch):
            backward_motor(delay=0.00003, steps=5, port=vertical_motor_ports)
            # forward_motor(delay=0.00003, steps=5, port=vertical_motor_$
        v_flag = 1
        print("vertical reset complete!")

    def service_mode(floor):
        global current_position, target_position, horizonal_step, vertical_step
        target_position = floor_position[floor]
        horizonal_step = int(1000 * (target_position[0] - current_position[0]) / 10.2)
        vertical_step = int(1000 * (target_position[1] - current_position[1]) / 10.2)

    def horizonal_act(step):
        global h_flag
        if step > 0:
            forward_motor(delay=0.00003, steps=step, port=horizonal_motor_ports)
        else if step < 0:
            backward_motor(delay=0.00003, steps=step, port=horizonal_motor_ports)
        h_flag = 1
        print("horizotal reset complete!")

    def vertical_act(step):
        global v_flag
        if step > 0:
            forward_motor(delay=0.00003, steps=step, port=vertical_motor_ports)
        else if step < 0:
            backward_motor(delay=0.00003, steps=step, port=vertical_motor_ports)
        v_flag = 1
        print("vertical reset complete!")

    def activate_motor(target_floors):
        global h_flag, v_flag
        h_flag = 0
        v_flag = 0
        th_horizonal_act = Thread(target = horizonal_act, daemon = Ture)
        th_vertical_act = Thread(target = vertical_act, daemon = Ture)
        th_horizonal_act.start()
        th_vertical_act.join()
        th_vertical_act.start()
        th_vertical_act.join()
        while not h_flag & v_flag:
            continue
        global current_position
        current_position = target_floors
        print("Step-motor moving complete!")

    def waiting_mode(self):
        global target_floors
        while len(target_floors) == 0:
            print("\rWaiting Mode", end = '')
            continue


if __name__ == '__main__':
    motor = StepMotor()
    while Ture:
        try:
            motor.stop_motor(horizonal_motor_ports)
            motor.stop_motor(vertical_motor_ports)
            motor.waiting_mode()
            pressing_target = target_floors.pop(0)
            motor.service_mode(pressing_target)
        except KeyboardInterrupterror:
            break
        except IndexError:
            time.sleep(2)
            continue
