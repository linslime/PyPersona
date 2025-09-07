from aip import AipSpeech
import time


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
        'spd': 7,
        })
        return result

if __name__ == '__main__':
    start = time.time()
    tts_runner = tts()
    result = tts_runner.run("大雁塔在西安南郊，也叫慈恩寺塔。他是唐代玄奘法师为保存佛经和舍利子建的。")
    end = time.time()
    print(end - start)
    file_name = './result' + str(time.time()) + '.wav'
    if not isinstance(result, dict):
        with open(file_name, 'wb') as f:
            f.write(result)
    # print(result)