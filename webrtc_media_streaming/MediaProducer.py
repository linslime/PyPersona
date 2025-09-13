import asyncio
from dialogue import dialogue
import soundfile as sf
import numpy as np
import cv2


class MediaProducer:

	def __init__(self, video_queue, audio_queue, audio_recorder_condition):
		self.audio_file_queue = asyncio.Queue(maxsize=1)
		self.audio_task_queue = asyncio.Queue(maxsize=1)
		self.video_task_queue = asyncio.Queue(maxsize=1)
		self.voiced_audio: "asyncio.Queue" = asyncio.Queue(maxsize=100)
		self.voiced_video: "asyncio.Queue" = asyncio.Queue(maxsize=10)
		self.silent_audio: "asyncio.Queue" = asyncio.Queue(maxsize=10)
		self.silent_video: "asyncio.Queue" = asyncio.Queue(maxsize=10)
		self.video_queue: "asyncio.Queue" = video_queue
		self.audio_queue: "asyncio.Queue" = audio_queue

		self.audio_recorder_condition = audio_recorder_condition
		self.state = "silent"
		self.state_lock = asyncio.Lock()
		self.video_state = "over"
		self.video_state_lock = asyncio.Lock()
		self.audio_state = "over"
		self.audio_state_lock = asyncio.Lock()

	async def task_producer(self) -> None:
		di = dialogue()

		while True:
			audio_file = await self.audio_file_queue.get()
			path = di.run(audio_file)
			await self.audio_task_queue.put(path)
			await self.video_task_queue.put(path)

	async def silent_audio_frames_producer(self) -> None:
		while True:
			await self.silent_audio.put(np.zeros((1024, 2), dtype=np.int16))

	async def voiced_audio_frames_producer(self, block_size: int = 1024) -> None:
		"""
		生产者: 读取 wav 音频, 按块(block_size)放入队列, 最后放 None 表示结束
		"""
		while True:
			path = await self.audio_task_queue.get()
			with sf.SoundFile(path, 'r') as f:
				while True:
					# 每次读 block_size 帧（每帧可能有多通道）
					data = f.read(block_size, dtype='int16')
					if data.size == 0:  # 读完了
						break
					await self.voiced_audio.put(data)
					self.audio_state = "start"
				self.audio_state = "over"

	async def silent_video_frames_producer(self) -> None:
		while True:
			cap = cv2.VideoCapture("/home/linslime/code/PyPersona/webrtc_media_streaming/sample_video.mp4")
			if not cap.isOpened():
				return

			while True:
				ret, frame = cap.read()
				if not ret:
					break
				await self.silent_video.put(frame)

			cap.release()

	async def voiced_video_frames_producer(self) -> None:
		async def silent_video_frame_generator(text: str):
			"""异步生成器：输入字符串，输出随机 numpy 数组 (512,512,3)"""
			for i in range(64):
				# 每次生成一帧随机图像
				arr = np.random.randint(0, 256, (512, 512, 3), dtype=np.uint8)
				yield arr
				await asyncio.sleep(0.1)  # 让出控制权
		while True:
			path = await self.video_task_queue.get()
			async for frame in silent_video_frame_generator(path):
				await self.voiced_video.put(frame)
				self.video_state = "start"
			self.video_state = "stop"

	async def audio_frames_producer(self) -> None:
		while True:
			audio_frame = None
			if self.state == "silent":
				audio_frame = await self.silent_audio.get()
			elif self.state == "voiced":
				audio_frame = await self.voiced_audio.get()
			await self.audio_queue.put(audio_frame)

	async def video_frames_producer(self) -> None:
		while True:
			video_frame = None
			if self.state == "silent":
				video_frame = await self.silent_video.get()
			elif self.state == "voiced":
				video_frame = await self.voiced_video.get()
			await self.video_queue.put(video_frame)

	async def async_guard(self) -> None:
		if self.state == "silent" and self.video_state == "start" and self.audio_state == "start":
			self.state = "start"
		elif self.state == "voiced" and self.video_state == "over" and self.audio_state == "over":
			self.state = "silent"
		await asyncio.sleep(0.3)


