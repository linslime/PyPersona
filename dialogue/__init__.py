from asr import asr
from llm import llm
from tts import tts
import time

class dialogue:
	def __init__(self):
		self.asr = asr()
		self.llm = llm()
		self.tts = tts()

	def run(self, path):
		query = self.asr.run(path)
		response = self.llm.run(query)
		wav = self.tts.run(response)
		file_name = './result' + str(time.time()) + '.wav'
		if not isinstance(wav, dict):
			with open(file_name, 'wb') as f:
				f.write(wav)


if __name__ == '__main__':
	di = dialogue()
	path = di.run("/home/linslime/code/PyPersona/ER-NeRF/data/task.wav")
