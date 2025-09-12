import asyncio
import soundfile as sf  # pip install soundfile
import numpy as np


async def audio_frames_queue(path: str, q: asyncio.Queue, block_size: int = 1024) -> None:
    """
    生产者: 读取 wav 音频, 按块(block_size)放入队列, 最后放 None 表示结束
    """
    while True:
        with sf.SoundFile(path, 'r') as f:
            while True:
                # 每次读 block_size 帧（每帧可能有多通道）
                data = f.read(block_size, dtype='int16')
                if data.size == 0:  # 读完了
                    break
                await q.put(data)


async def print_audio_info_from_queue(q: asyncio.Queue) -> None:
    """
    消费者: 从队列取音频块并打印信息; 收到 None 时结束
    """
    while True:
        block = await q.get()
        print(f"Block dtype: {block.dtype}, shape: {block.shape}")


async def main():
    q = asyncio.Queue(maxsize=10)

    producer = asyncio.create_task(audio_frames_queue(
        "/home/linslime/code/PyPersona/webrtc_media_streaming/sample_audio.wav", q
    ))
    consumer = asyncio.create_task(print_audio_info_from_queue(q))

    await asyncio.gather(producer, consumer)


if __name__ == "__main__":
    asyncio.run(main())
