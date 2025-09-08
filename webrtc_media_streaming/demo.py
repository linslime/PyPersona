# server_demo.py
import asyncio
import threading
import time
import os
from typing import Optional, Tuple

import numpy as np
import av  # PyAV
from av.audio.resampler import AudioResampler
from av.video.frame import VideoFrame
from av.audio.frame import AudioFrame

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack

# ===================== 配置：改成你的文件路径 =====================
# 支持常见格式：mp4/mov/mkv/avi（视频），mp3/aac/m4a/wav/flac（音频）
VIDEO_PATH = os.environ.get("VIDEO_PATH", "demo_video.mp4")
AUDIO_PATH = os.environ.get("AUDIO_PATH", "/home/linslime/code/PyPersona/data/response_tts_20250908155557.wav")

# 目标音频参数（WebRTC 友好）
TARGET_SR = 48000
TARGET_CH = 2          # 立体声
AUDIO_BLOCK = 960      # 每块 960 样本 = 20ms（@48kHz）

# 视频节流（若源是可变帧率，按帧时间睡眠；可设定最小/最大帧间隔）
MIN_FRAME_INTERVAL = 1.0 / 120.0
MAX_FRAME_INTERVAL = 1.0 / 5.0

# ===================== 内存队列 =====================
video_q: "asyncio.Queue[np.ndarray]" = asyncio.Queue(maxsize=90)   # HxWx3, uint8, RGB
audio_q: "asyncio.Queue[np.ndarray]" = asyncio.Queue(maxsize=480)  # (samples, channels), float32 in [-1,1]

# ===================== 同步起播时钟 =====================
class SyncClock:
    def __init__(self):
        self._start_time: Optional[float] = None
        self._audio_ready = asyncio.Event()
        self._video_ready = asyncio.Event()

    def mark_audio_ready(self):
        self._audio_ready.set()

    def mark_video_ready(self):
        self._video_ready.set()

    async def wait_both_ready(self):
        await asyncio.gather(self._audio_ready.wait(), self._video_ready.wait())
        if self._start_time is None:
            self._start_time = time.monotonic()
        return self._start_time

    @property
    def start_time(self) -> Optional[float]:
        return self._start_time

sync_clock = SyncClock()

# ===================== 自定义 Tracks =====================
class MemoryVideoTrack(MediaStreamTrack):
    kind = "video"
    def __init__(self):
        super().__init__()
        self.time_base = av.Rational(1, 90000)

    async def recv(self) -> VideoFrame:
        if sync_clock.start_time is None:
            sync_clock.mark_video_ready()
            await sync_clock.wait_both_ready()

        arr = await video_q.get()  # RGB uint8
        frame = VideoFrame.from_ndarray(arr, format='rgb24')

        elapsed = time.monotonic() - sync_clock.start_time
        frame.pts = int(elapsed * 90000)
        frame.time_base = self.time_base
        return frame

class MemoryAudioTrack(MediaStreamTrack):
    kind = "audio"
    def __init__(self, sample_rate: int = TARGET_SR, channels: int = TARGET_CH):
        super().__init__()
        self.sample_rate = sample_rate
        self.channels = channels
        self.time_base = av.Rational(1, sample_rate)
        self._cursor = 0  # 累计样本

    async def recv(self) -> AudioFrame:
        if sync_clock.start_time is None:
            sync_clock.mark_audio_ready()
            await sync_clock.wait_both_ready()

        chunk = await audio_q.get()  # float32 (N, C)
        if chunk.dtype != np.float32:
            chunk = chunk.astype(np.float32)

        if chunk.ndim == 1 and self.channels > 1:
            chunk = np.repeat(chunk[:, None], self.channels, axis=1)

        # planar float
        frame = AudioFrame(format='flt', layout='stereo' if self.channels == 2 else 'mono',
                           samples=chunk.shape[0])
        for ch in range(self.channels):
            data = chunk[:, ch].copy()
            frame.planes[ch].update(data.tobytes())

        frame.pts = self._cursor
        frame.sample_rate = self.sample_rate
        frame.time_base = self.time_base

        self._cursor += chunk.shape[0]
        return frame

# ===================== FastAPI: WebRTC 信令 =====================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

pcs = set()

class SDPModel(BaseModel):
    sdp: str
    type: str

@app.post("/offer")
async def offer_endpoint(sdp_in: SDPModel):
    pc = RTCPeerConnection(configuration={
        "iceServers": [
            {"urls": ["stun:stun.l.google.com:19302"]},
            # 如需 TURN:
            # {"urls": ["turn:your.turn.server:3478"], "username": "user", "credential": "pass"}
        ]
    })
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_state_change():
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            pcs.discard(pc)

    pc.addTrack(MemoryVideoTrack())
    pc.addTrack(MemoryAudioTrack())

    offer = RTCSessionDescription(sdp=sdp_in.sdp, type=sdp_in.type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

# ===================== 生产者：文件 -> 队列 =====================
def _safe_sleep(dt: float):
    if dt > 0:
        time.sleep(dt)

def video_producer_loop(path: str):
    """
    解码视频 -> RGB ndarray -> 按帧时间（或估计间隔）推入 video_q
    若播放到尾部，自动循环。
    """
    while True:
        try:
            with av.open(path) as container:
                stream = next((s for s in container.streams if s.type == 'video'), None)
                if stream is None:
                    print("[VIDEO] No video stream found.")
                    time.sleep(1)
                    continue

                # 有些文件的时间基和帧率不可靠，用帧 pts 差值做 pacing
                prev_ts = None
                for frame in container.decode(stream):
                    # 转 RGB
                    rgb = frame.to_ndarray(format='rgb24')  # HxWx3, uint8

                    # 推入队列（丢旧保新）
                    try:
                        video_q.put_nowait(rgb)
                    except asyncio.QueueFull:
                        try:
                            _ = video_q.get_nowait()
                        except Exception:
                            pass
                        video_q.put_nowait(rgb)

                    # 计算帧间隔
                    ts = float(frame.pts * frame.time_base) if (frame.pts is not None and frame.time_base is not None) else None
                    if prev_ts is not None and ts is not None:
                        dt = ts - prev_ts
                    else:
                        # 退化：估计 30fps
                        dt = 1.0 / 30.0
                    prev_ts = ts if ts is not None else (prev_ts + dt if prev_ts is not None else 0.0)

                    dt = max(MIN_FRAME_INTERVAL, min(MAX_FRAME_INTERVAL, dt))
                    _safe_sleep(dt)
        except av.AVError as e:
            print(f"[VIDEO] AVError: {e}; retry in 1s...")
            time.sleep(1)
        except FileNotFoundError:
            print(f"[VIDEO] File not found: {path}; retry in 1s...")
            time.sleep(1)

def chunk_audio_to_blocks(arr_f32_stereo: np.ndarray, block: int = AUDIO_BLOCK) -> Tuple[np.ndarray, int]:
    """
    输入: float32, shape=(N, 2)
    输出: 若 N >= block, 返回 arr[:k*block], k （整块数量）
    """
    n = arr_f32_stereo.shape[0]
    k = n // block
    if k == 0:
        return np.empty((0, 2), dtype=np.float32), 0
    return arr_f32_stereo[:k*block], k

def audio_producer_loop(path: str):
    """
    解码音频 -> 重采样到 48k 立体声 -> 每 960 样本分块 -> 推入 audio_q
    按 20ms 块节流。
    """
    resampler = AudioResampler(format='flt', layout='stereo', rate=TARGET_SR)
    carry = np.empty((0, TARGET_CH), dtype=np.float32)

    while True:
        try:
            with av.open(path) as container:
                stream = next((s for s in container.streams if s.type == 'audio'), None)
                if stream is None:
                    print("[AUDIO] No audio stream found.")
                    time.sleep(1)
                    continue

                # 对某些容器，解码会产生一批批 AudioFrame
                for frame in container.decode(stream):
                    # 重采样到 flt stereo 48k
                    frames = resampler.resample(frame)
                    if not isinstance(frames, list):
                        frames = [frames] if frames is not None else []

                    for f in frames:
                        # f.to_ndarray(): (channels, samples) -> 转置为 (samples, channels)
                        # 注意：有时 PyAV 返回的是 (samples, channels)，若维度对不上，转置处理
                        arr = f.to_ndarray()
                        if arr.ndim == 2:
                            if arr.shape[0] == TARGET_CH:
                                arr = arr.T  # (samples, 2)
                            elif arr.shape[1] == TARGET_CH:
                                pass  # already (samples, 2)
                            else:
                                # 尝试修正到立体声
                                if arr.shape[0] == 1:
                                    arr = np.repeat(arr.T, 2, axis=1)
                                elif arr.shape[1] == 1:
                                    arr = np.repeat(arr, 2, axis=1)
                                else:
                                    # 兜底：取前两声道
                                    arr = arr.T[:, :2] if arr.shape[0] >= 2 else arr[:, :2]
                        else:
                            # 兜底：视为单声道
                            arr = np.expand_dims(arr, axis=1)
                            arr = np.repeat(arr, 2, axis=1)

                        arr = arr.astype(np.float32)

                        # 与 carry 拼接后按 960 一块分发
                        carry = np.concatenate([carry, arr], axis=0)
                        blocks, k = chunk_audio_to_blocks(carry, AUDIO_BLOCK)
                        if k > 0:
                            # 推送 k 块；节流到每块 20ms
                            for i in range(k):
                                block_arr = blocks[i*AUDIO_BLOCK:(i+1)*AUDIO_BLOCK]
                                try:
                                    audio_q.put_nowait(block_arr)
                                except asyncio.QueueFull:
                                    try:
                                        _ = audio_q.get_nowait()
                                    except Exception:
                                        pass
                                    audio_q.put_nowait(block_arr)
                                _safe_sleep(AUDIO_BLOCK / TARGET_SR)
                            carry = carry[k*AUDIO_BLOCK:]
                # 文件播完：循环
        except av.AVError as e:
            print(f"[AUDIO] AVError: {e}; retry in 1s...")
            time.sleep(1)
        except FileNotFoundError:
            print(f"[AUDIO] File not found: {path}; retry in 1s...")
            time.sleep(1)

# ===================== 入口 =====================
def main():
    # 启动文件生产者（后台线程）
    threading.Thread(target=video_producer_loop, args=(VIDEO_PATH,), daemon=True).start()
    threading.Thread(target=audio_producer_loop, args=(AUDIO_PATH,), daemon=True).start()

    # 启动 FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    main()
