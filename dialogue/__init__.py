from asr import asr
from llm import llm
from tts import tts
from datetime import datetime

class dialogue:
	def __init__(self):
		self.asr = asr()
		self.llm = llm()
		self.tts = tts()

	def run(self, path):
		query = self.asr.run(path)
		response = self.llm.run(query)
		wav = self.tts.run(response)
		return wav

if __name__ == '__main__':
	di = dialogue()
	path = di.run("/home/linslime/code/PyPersona/data/query.wav")
