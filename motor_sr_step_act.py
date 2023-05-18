from huaweicloud_sis.client.rasr_client import RasrClient
from huaweicloud_sis.bean.rasr_request import RasrRequest
from huaweicloud_sis.bean.callback import RasrCallBack
from huaweicloud_sis.bean.sis_config import SisConfig
import time, os, sys, json, threading, base64
from threading import Thread, Lock
import RPi.GPIO as gpio
import websocket
import pyaudio
import wave

floor = 0
# floor = [1, 2, 3, 6]
gpio.setwarnings(False)
gpio.setmode(gpio.BOARD)
# rasp_pin:
# 2 step motor driver:
vertical_PUL0 = 11  # 32  # GPIO26 BCM12
vertical_PUL1 = 22  # 36  # GPIO27 BCM16
vertical_DIR0 = 32  # 38  # GPIO28 BCM20
vertical_DIR1 = 36  # 40  # GPIO29 BCM21
horizon_PUL0 = 29  # 31  # GPIO22 BCM6
horizon_PUL1 = 31  # 33  # GPIO23 BCM13
horizon_DIR0 = 33  # 35  # GPIO24 BCM19
horizon_DIR1 = 37  # GPIO25 BCM26
# FAN = [4, 6]
innner_ele_mag = 16  # 29  # floor pressing module GPIO21 BCM5
upstair_ele_mag = 13  # GPIO2 BCM27
downstair_ele_mag = 15  # GPIO3 BCM22
vertical_reset_switch = 18  # BCM23
horizon_reset_switch = 7  # BCM24

# floor_num_trans
floor_position = [[0, 0],
                  [32, -132.25], [32, -92.75],
                  [32, -53.25], [32, -13.75],
                  [103, -132.25], [103, -92.75],
                  [103, -53.25], [103, -13.75]]
# original position and floors' (mm)
current_position = [0, 0]
target_position = [0, 0]
sr_flag = 1
v_flag = 0
h_flag = 0
horizontal_motor_ports = [horizon_PUL0, horizon_PUL1, horizon_DIR0, horizon_DIR1]
vertical_motor_ports = [vertical_PUL0, vertical_PUL1, vertical_DIR0, vertical_DIR1]  # the pins of step motor driver
for pm in (vertical_motor_ports + horizontal_motor_ports):
    gpio.setup(pm, gpio.OUT)  # set step motor driver pin mode
ele_port = [innner_ele_mag, upstair_ele_mag, downstair_ele_mag]
for pe in ele_port:
    gpio.setup(pe, gpio.OUT)  # GPIO ELE_MAG 26 (Pin 37)
gpio.setup(vertical_reset_switch, gpio.IN, pull_up_down=gpio.PUD_UP)
gpio.setup(horizon_reset_switch, gpio.IN, pull_up_down=gpio.PUD_DOWN)


# 鉴权信息
ak = 'YFUNLQ0KHQVVX3TAHEWW'  # 用户的ak
sk = '9T4rOtBRNM9DkMjxIvxG9LqcDn4ka1U4LFJ8lzEs'  # 用户的sk
region = 'cn-east-3'  # region，如cn-north-4(peking 4), cn-east-3(shanghai 1)
project_id = '0accfa0d2d80f28a2f2bc0129988145d'
# 同region一一对应，参考 https://support.huaweicloud.com/api-sis/sis_03_0008.html

# 实时语音识别参数
# path = "recorded_sr.wav"
# 需要发送音频路径，如D:/test.pcm, 同时sdk也支持byte流发送数据。
audio_format = 'pcm16k16bit'
# pcm ulaw alaw, 16k 8k, 16bit 8bit
# 音频支持格式，详见api文档
property = 'chinese_16k_common'
# 属性字符串，language_sampleRate_domain, 如chinese_16k_general, 采样率要和音频一致。详见api文档

FORMAT = pyaudio.paInt16
CHANNELS = 1
CHUNK = 1024
RATE = 16000  # Hz
audio = pyaudio.PyAudio()

frames = []
frames_play = []
files_port = []
bytearray(frames)
used_files = []
recognition_results = ''
target_floors = {0, }
checking_string_set = [(),
                       ('1', '一', '一楼'),
                       ('2', '二', '两'),
                       ('3', '三', '汕头', '山城'),
                       ('4', '四', '去世', '是咯'),
                       ('5', '五'),
                       ('6', '六', '去留', '有'),
                       ('7', '七', '七楼'),
                       ('8', '八', '去吧', '灯笼'),
                       ('上', ),
                       ('下', )]
stream = audio.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    # output=True,
                    input_device_index=2,
                    # output_device_index=1,
                    frames_per_buffer=CHUNK)


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


def adding_floors(text_result):
    global sr_flag
    judging_string = text_result
    for index in range(1, 9):
        for target in checking_string_set[index]:
            if target in judging_string:
                target_floors.add(index)
                sr_flag = 0
                break
    #print(target_floors)


class MyCallback(RasrCallBack):
    """ 回调类，用户需要在对应方法中实现自己的逻辑，其中on_response必须重写 """
    def on_open(self):
        """ websocket连接成功会回调此函数 """
        print('websocket connect success')

    def on_start(self, message):
        """
            websocket 开始识别回调此函数
        :param message: 传入信息
        :return: -
        """
        print('webscoket start to recognize, %s' % message)

    def on_response(self, message):
        global recognition_results
        """
            websockert返回响应结果会回调此函数
        :param message: json格式
        :return: -
        """
        # print(json.dumps(message, indent=2, ensure_ascii=False))
        text_result = str(message['segments'][0]['result']['text'])
        print(text_result)
        adding_floors(text_result)# recognition_results += text_result


    def on_end(self, message):
        """
            websocket 结束识别回调此函数
        :param message: 传入信息
        :return: -
        """
        print('websocket is ended, %s' % message)

    def on_close(self):
        """ websocket关闭会回调此函数 """
        print('websocket is closed')

    def on_error(self, error):
        """
            websocket出错回调此函数
        :param error: 错误信息
        :return: -
        """
        print('websocket meets error, the error is %s' % error)


def rasr_example():
    """ 实时语音识别demo """
    # step1 初始化RasrClient, 暂不支持使用代理
    my_callback = MyCallback()
    config = SisConfig()
    # 设置连接超时,默认是10
    config.set_connect_timeout(10)
    # 设置读取超时, 默认是10
    config.set_read_timeout(10)
    # 设置connect lost超时，一般在普通并发下，不需要设置此值。默认是4
    config.set_connect_lost_timeout(4)
    # websocket暂时不支持使用代理
    rasr_client = RasrClient(ak=ak, sk=sk, use_aksk=True, region=region, project_id=project_id,
                             callback=my_callback, config=config)
    # step2 构造请求
    request = RasrRequest(audio_format, property)
    # 所有参数均可不设置，使用默认值
    request.set_add_punc('no')  # 设置是否添加标点， yes or no， 默认no
    request.set_vad_head(20000)  # 设置有效头部， [0, 60000], 默认10000
    request.set_vad_tail(500)  # 设置有效尾部，[0, 3000]， 默认500
    request.set_max_seconds(60)  # 设置一句话最大长度，[0, 60], 默认30
    request.set_interim_results('no')  # 设置是否返回中间结果，yes or no，默认no1
    request.set_digit_norm('no')  # 设置是否将语音中数字转写为阿拉伯数字，yes or no，默认yes
    # request.set_vocabulary_id('')     # 设置热词表id，若不存在则不填写，否则会报错
    # step3 选择连接模式
    rasr_client.continue_stream_connect(request)  # 实时语音识别连续模式
    # step4 發送數據
    send_record(rasr_client)
    # step5 关闭客户端，使用完毕后一定要关闭，否则服务端20s内没收到数据会报错并主动断开。
    rasr_client.close()


def send_record(rasr_client):
    # step4 发送音频
    # 连续模式下，可多次发送音频，发送格式为byte数组
    global frames
    rasr_client.send_start()
    b = 0
    while sr_flag:
        if len(frames) > 0:
            try:
                send_data = frames.pop(0)
            except IndexError:
                continue
            rasr_client.send_audio(data=send_data, byte_len=3000, sleep_time=0.02)
    rasr_client.send_end()


def record():
    print("* recording")
    global frames
    while sr_flag:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)


if __name__ == '__main__':
    th_vertical_reset = Thread(target=vertical_motor_reset)
    th_horizon_reset = Thread(target=horizon_motor_reset)
    th_vertical_reset.start()
    th_horizon_reset.start()
    while not (h_flag & v_flag):
        continue
    print("Step-motor initialized!")
    while True:
        complete_flag = 1
        th_record = Thread(target=record)
        th_senddata = Thread(target=rasr_example)
        th_record.start()
        th_senddata.start()

        # for i in floor:
        while complete_flag:
            if not sr_flag:
                i = int(input())
                print(i)
                service_mode(i)
                if current_position != [0, 0]:
                    time.sleep(0.2)
                    ele_mag_act(0)
                time.sleep(0.5)
                complete_flag = 0
