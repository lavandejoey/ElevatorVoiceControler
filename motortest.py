import RPi.GPIO as gpio
from threading import Thread
import time
floor = 0
# floor = [1, 2, 3, 6]
gpio.setwarnings(False)
gpio.setmode(gpio.BOARD)
# rasp_pin:
# 2 step motor driver:
vertical_PUL0 = 32  # GPIO26 BCM12
vertical_PUL1 = 36  # GPIO27 BCM16
vertical_DIR0 = 38  # GPIO28 BCM20
vertical_DIR1 = 40  # GPIO29 BCM21
horizon_PUL0 = 31  # GPIO22 BCM6
horizon_PUL1 = 33  # GPIO23 BCM13
horizon_DIR0 = 35  # GPIO24 BCM19
horizon_DIR1 = 37  # GPIO25 BCM26
# FAN = [4, 6]
innner_ele_mag = 29  # floor pressing module GPIO21 BCM5
upstair_ele_mag = 13  # GPIO2 BCM27
downstair_ele_mag = 15  # GPIO3 BCM22
vertical_reset_switch = 16  # BCM23
horizon_reset_switch = 18  # BCM24

# floor_num_trans
floor_position = [[0, 0],
                  [31, -118.5], [31, -79],
                  [31, -39.5], [31, 0],
                  [101.5, -118.5], [101.5, -79],
                  [101.5, -39.5], [101.5, 0]]
# original position and floors' (mm)
current_position = [0, 0]
target_position = [0, 0]

v_flag = 0
h_flag = 0
horizontal_motor_ports = [horizon_PUL0, horizon_PUL1, horizon_DIR0, horizon_DIR1]
vertical_motor_ports = [vertical_PUL0, vertical_PUL1, vertical_DIR0, vertical_DIR1]  # the pins of step motor driver
for pm in (vertical_motor_ports + horizontal_motor_ports):
    gpio.setup(pm, gpio.OUT)  # set step motor driver pin mode
ele_port = [innner_ele_mag, upstair_ele_mag, downstair_ele_mag]
for pe in ele_port:
    gpio.setup(pe, gpio.OUT)  # GPIO ELE_MAG 26 (Pin 37)
gpio.setup(vertical_reset_switch, gpio.IN, pull_up_down=gpio.PUD_DOWN)
gpio.setup(horizon_reset_switch, gpio.IN, pull_up_down=gpio.PUD_DOWN)


def set_motor_step(mode1, mode2, mode3, mode4, port):  # moving on
    modes = [mode1, mode2, mode3, mode4]
    si = 0
    for pin in port:
        gpio.output(pin, modes[si])
        si += 1


def stop_motor(port):
    set_motor_step(0, 0, 0, 0, port)


def backward_motor(delay, steps, port):
    for bi in range(0, steps):
        set_motor_step(1, 0, 1, 0, port)
        time.sleep(delay)
        set_motor_step(0, 1, 1, 0, port)
        time.sleep(delay)
        set_motor_step(0, 1, 0, 1, port)
        time.sleep(delay)
        set_motor_step(1, 0, 0, 1, port)
        time.sleep(delay)


def forward_motor(delay, steps, port):  # right for horizon, up for vertical
    for fi in range(0, steps):
        set_motor_step(1, 0, 0, 1, port)
        time.sleep(delay)
        set_motor_step(0, 1, 0, 1, port)
        time.sleep(delay)
        set_motor_step(0, 1, 1, 0, port)
        time.sleep(delay)
        set_motor_step(1, 0, 1, 0, port)
        time.sleep(delay)


def vertical_motor_reset():
    while not gpio.input(vertical_reset_switch):
        # backward_motor(delay=0.00003, steps=5, port=vertical_motor_ports)
        forward_motor(delay=0.00003, steps=5, port=vertical_motor_ports)
    stop_motor(vertical_motor_ports)
    global v_flag
    v_flag = 1
    print("vertical reset complete!")


def horizon_motor_reset():
    while not gpio.input(horizon_reset_switch):
        backward_motor(delay=0.00003, steps=5, port=horizontal_motor_ports)
        # forward_motor(delay=0.00003, steps=5, port=horizontal_motor_ports)
    stop_motor(horizontal_motor_ports)
    global h_flag
    h_flag = 1
    print("horizontal reset complete!")


def horizontal_act():
    global h_flag
    step = horizontal_step
    if step > 0:  # right
        forward_motor(delay=0.00003, steps=step, port=horizontal_motor_ports)
    elif step < 0:  # left
        step = abs(step)
        backward_motor(delay=0.00003, steps=step, port=horizontal_motor_ports)
    h_flag = 1
    print("horizontal moving complete!")


def vertical_act():
    global v_flag
    step = vertical_step
    if step > 0:  # up
        forward_motor(delay=0.00003, steps=step, port=vertical_motor_ports)
    elif step < 0:  # down
        step = abs(step)
        backward_motor(delay=0.00003, steps=step, port=vertical_motor_ports)
    v_flag = 1
    print("vertical moving complete!")


def service_mode(fl):
    global current_position, target_position, horizontal_step, vertical_step
    target_position = floor_position[fl]
    horizontal_step = int(1000 * (target_position[0] - current_position[0]) / 10.2)
    vertical_step = int(1000 * (target_position[1] - current_position[1]) / 19.865)
    print(horizontal_step, vertical_step)
    current_position = target_position
    activate_motor()


def activate_motor():
    global h_flag, v_flag
    h_flag = 0
    v_flag = 0
    th_horizontal_act = Thread(target=horizontal_act)
    th_horizontal_act.setDaemon(True)
    th_vertical_act = Thread(target=vertical_act)
    th_vertical_act.setDaemon(True)
    th_horizontal_act.start()
    th_vertical_act.start()
    th_horizontal_act.join()
    th_vertical_act.join()
    while not (h_flag & v_flag):
        continue
    print("Step-motor moving complete!")


def ele_mag_act(mode=0):
    activated_ele_mag = ele_port[mode]
    try:
        gpio.output(activated_ele_mag, True)
        time.sleep(0.8)
        gpio.output(activated_ele_mag, False)
        return 1
    except BlockingIOError:
        return 0


if __name__ == '__main__':
    th_vertical_reset = Thread(target=vertical_motor_reset)
    th_vertical_reset.setDaemon(True)
    th_horizon_reset = Thread(target=horizon_motor_reset)
    th_horizon_reset.setDaemon(True)
    th_vertical_reset.start()
    th_horizon_reset.start()
    th_vertical_reset.join()
    th_horizon_reset.join()
    while not (h_flag & v_flag):
        continue
    print("Step-motor initialized!")
    # for i in floor:
    while True:
        i = input()
        print(i)
        service_mode(i)
        time.sleep(0.2)
        ele_mag_act(0)
        time.sleep(0.5)

