import av
from aiortc.contrib.media import MediaRecorderContext, MediaPlayer, MediaStreamError
from aiortc.contrib.media import MediaRecorder
import numpy as np
import time
import asyncio


class AudioRecorder:

	def __init__(self, file, format=None, options=None):
		self.__container = av.open(file=file, format=format, mode="w", options=options)

	def start(self):
		codec_name = "pcm_s16le"
		stream = self.__container.add_stream(codec_name)
		self.__media_recorder_context = MediaRecorderContext(stream)

	def stop(self):
		if self.__container:
			if self.__media_recorder_context.task is not None:
				self.__media_recorder_context.task.cancel()
				self.__media_recorder_context.task = None
				for packet in self.__media_recorder_context.stream.encode(None):
					self.__container.mux(packet)
			if self.__container:
				self.__container.close()
				self.__container = None

	def add_frame(self, frame):
		for packet in self.__media_recorder_context.stream.encode(frame):
			self.__container.mux(packet)


class AudioDynamicRecorder:
	Volume_Threshold = 5000

	def __init__(self, track, condition, wav_file):
		self.__track = track
		self.__condition: asyncio.Condition = condition
		self.__wav_file: asyncio.Queue = wav_file

	async def start(self):
		asyncio.ensure_future(self.__receive_audio())

	async def __receive_audio(self):
		state = 0
		true_flag = -1
		false_flag = -1
		current_audio_recorder = None
		file_name = None
		while True:
			frame = await self.__track.recv()
			max_ = np.absolute(frame.to_ndarray()).max()
			if state == 0:
				if max_ >= self.Volume_Threshold:
					file_name = './task' + str(time.time()) + '.wav'
					current_audio_recorder = AudioRecorder(file_name)
					current_audio_recorder.start()
					current_audio_recorder.add_frame(frame)
					true_flag = frame.pts
					state = 1
			elif state == 1:
				current_audio_recorder.add_frame(frame)
				if max_ < self.Volume_Threshold:
					state = 2
					false_flag = frame.pts
			elif state == 2:
				current_audio_recorder.add_frame(frame)
				if max_ >= self.Volume_Threshold:
					state = 1
					false_flag = -1
				else:
					if frame.pts - false_flag > 10000:
						if frame.pts - true_flag > 30000:
							current_audio_recorder.stop()
							await self.__wav_file.put(file_name)
							await self.__condition.wait()
						state = 0
						false_flag = -1
