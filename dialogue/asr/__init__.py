import whisper


class asr:
	def __init__(self):
		self.model = whisper.load_model(name='base', device='cuda')

	def run(self, speech):
		return self.model.transcribe(speech, language='zh', fp16=False)["text"]


if __name__ == '__main__':
	import time
	start = time.time()
	asr_runner = asr()
	result = asr_runner.run("/home/linslime/code/PyPersona/ER-NeRF/data/task.wav")
	end = time.time()
	print(end - start)
	print(result)
