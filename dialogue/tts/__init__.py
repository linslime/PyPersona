from aip import AipSpeech
import time
from io import BytesIO
from pydub import AudioSegment
from datetime import datetime
import os


class tts:
    """ 你的 APPID AK SK """
    APP_ID = '116326641'
    API_KEY = 'pXxzzKwORSnRqLv16MPKzCbt'
    SECRET_KEY = 'd3WH7vVG8UG2VbfsZDRcMQryLifOYFrZ'

    client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)

    def run(self, text):
        result = self.client.synthesis(text, 'zh', 1, {
        'vol': 5,
        'per': 1,
        'spd': 9,
        })
        mp3_stream = BytesIO(result)
        audio = AudioSegment.from_file(mp3_stream, format="mp3")
        audio = audio.set_frame_rate(44100).set_channels(1)
        audio_path = os.environ.get("PROJECT_ROOT") + '/data/media/response_audio_' + datetime.now().strftime("%Y%m%d%H%M%S") + '.wav'
        audio.export(audio_path, format="wav")
        return audio_path


if __name__ == '__main__':
    start = time.time()
    tts_runner = tts()
    result = tts_runner.run("大雁塔在西安南郊，也叫慈恩寺塔。他是唐代玄奘法师为保存佛经和舍利子建的。")
    end = time.time()
    print(end - start)
