from huaweicloud_sis.client.rasr_client import RasrClient
from huaweicloud_sis.bean.rasr_request import RasrRequest
from huaweicloud_sis.bean.callback import RasrCallBack
from huaweicloud_sis.bean.sis_config import SisConfig
import time, os, sys, json, threading, base64
from threading import Thread, Lock
# import RPi.GPIO as gpio
import websocket
import pyaudio
import wave

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

# for i in range(audio.get_device_count()):
#     print(json.dumps(audio.get_device_info_by_index(i), indent=2))

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
#                    input_device_index=2,
                    # output_device_index=1,
                    frames_per_buffer=CHUNK)


def adding_floors(text_result):
    judging_string = text_result
    for target in checking_string_set[1]:
        if target in judging_string:
            target_floors.add(1)
            break
    for target in checking_string_set[2]:
        if target in judging_string:
            target_floors.add(2)
            break
    for target in checking_string_set[3]:
        if target in judging_string:
            target_floors.add(3)
            break
    for target in checking_string_set[4]:
        if target in judging_string:
            target_floors.add(4)
            break
    for target in checking_string_set[5]:
        if target in judging_string:
            target_floors.add(5)
            break
    for target in checking_string_set[6]:
        if target in judging_string:
            target_floors.add(6)
            break
    for target in checking_string_set[7]:
        if target in judging_string:
            target_floors.add(7)
            break
    for target in checking_string_set[8]:
        if target in judging_string:
            target_floors.add(8)
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
    request.set_vad_head(10000)  # 设置有效头部， [0, 60000], 默认10000
    request.set_vad_tail(300)  # 设置有效尾部，[0, 3000]， 默认500
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
    while True:
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
    while True:
        data = stream.read(CHUNK, exception_on_overflow = False)
        frames.append(data)


def cleaner():
    while True:
        try:
            used_file_path = used_files.pop(0)
            os.remove(used_file_path)
        except IndexError:
            time.sleep(1)
            continue


def simul_elevator():
    global target_floors
    while True:
        if len(target_floors) > 0:
            flo = target_floors.pop()
            print("activate")
            print("按 %d 楼" % flo)
        continue


if __name__ == '__main__':
    th_record = Thread(target=record)
    th_senddata = Thread(target=rasr_example)
    th_simul = Thread(target=simul_elevator)
    th_record.start()
    th_senddata.start()
    th_clean = Thread(target=cleaner)
    th_clean.start()
    th_simul.start()
