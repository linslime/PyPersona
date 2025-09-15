import asyncio
from fractions import Fraction
from typing import Optional

import numpy as np
from av import VideoFrame, AudioFrame
from aiortc import MediaStreamTrack


class VideoStreamTrack(MediaStreamTrack):
    """
    从 asyncio.Queue[np.ndarray] 读取帧，按固定 fps 向下游发送。

    - 队列元素必须是 HxWxC 的 numpy.ndarray（C=3），例如 BGR 或 RGB。
    - 默认像素格式是 'bgr24'（OpenCV 常见），如你是 RGB 就传 'rgb24'。
    - PTS 以 time_base = 1/fps 递增（每帧 +1）。
    """

    kind = "video"

    def __init__(
        self,
        queue: "asyncio.Queue[np.ndarray]",
        fps: int = 25,
        frame_format: str = "bgr24",
        pace: bool = True,
    ):
        """
        :param queue: 装着 numpy 帧的异步队列（建议用 janus.Queue.async_q）
        :param fps: 输出帧率，默认 25
        :param frame_format: numpy 帧对应的像素格式（'bgr24' 或 'rgb24' 等）
        :param pace: 是否在 recv() 内按 fps 匀速输出（True 更平滑）
        """
        super().__init__()
        self.queue = queue
        self.fps = fps
        self.time_base = Fraction(1, fps)
        self._pts = 0
        self._dt = 1.0 / fps
        self._frame_format = frame_format
        self._pace = pace
        self._next_wallclock_ts: Optional[float] = None

    async def recv(self) -> VideoFrame:
        # 从队列拿到一帧（协程阻塞等待）
        arr: np.ndarray = await self.queue.get()

        # 按需节流以匹配 fps（可关）
        if self._pace:
            now = asyncio.get_event_loop().time()
            if self._next_wallclock_ts is None:
                self._next_wallclock_ts = now + self._dt
            else:
                # 如果现在比计划时间早，稍等；若晚了就直接发，避免堆积
                sleep_s = self._next_wallclock_ts - now
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)
                self._next_wallclock_ts += self._dt

        # ndarray -> VideoFrame
        vf = VideoFrame.from_ndarray(arr, format=self._frame_format)
        vf.pts = self._pts
        vf.time_base = self.time_base

        # 递增 pts
        self._pts += 1

        return vf


class AudioStreamTrack(MediaStreamTrack):
    """
    从 asyncio.Queue[np.ndarray] 读取音频帧（形状 1764x1，dtype=int16，单声道），
    以 25 fps 向下游发送（含匀速节流）。采样率固定 44100 Hz。
    """

    kind = "audio"

    def __init__(self, queue: "asyncio.Queue", fps: int = 25, pace: bool = True):
        super().__init__()
        self.queue = queue
        self.samplerate = 44100
        self.channels = 1
        self.samples_per_frame = 1764   # 44100 / 25
        self.time_base = Fraction(1, self.samplerate)
        self._pts = 0

        # 节流参数
        self._pace = pace
        self._dt = 1.0 / fps            # 帧间隔（秒）
        self._next_wallclock_ts = None  # 下次发送的目标时间戳（墙钟时间）

    async def recv(self) -> AudioFrame:
        # 取一帧 (1764,1) int16
        arr = await self.queue.get()

        if arr.shape[0] < self.samples_per_frame:
            temp_arr = np.zeros((self.samples_per_frame,), dtype=arr.dtype)
            temp_arr[:arr.shape[0]] = arr
            arr = temp_arr

        print(arr.shape)
        # 匀速节流：尽量按 25fps 等间隔输出
        if self._pace:
            now = asyncio.get_event_loop().time()
            if self._next_wallclock_ts is None:
                # 第一帧：从“现在”开始对齐
                self._next_wallclock_ts = now + self._dt
            else:
                # 若比计划时间早，就等到计划时间；晚了则不等，直接发，避免堆积
                sleep_s = self._next_wallclock_ts - now
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)
                self._next_wallclock_ts += self._dt

        # 组装 AudioFrame（单声道、s16）
        frame = AudioFrame(format="s16", layout="mono", samples=self.samples_per_frame)
        frame.sample_rate = self.samplerate
        frame.planes[0].update(arr.tobytes())

        # 时间戳：time_base=1/samplerate，PTS 以“样本”为单位累加
        frame.time_base = self.time_base
        frame.pts = self._pts
        self._pts += self.samples_per_frame

        return frame
