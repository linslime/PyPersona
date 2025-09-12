import asyncio
import cv2


async def video_frames_queue(path: str, q: asyncio.Queue) -> None:
    """
    生产者: 读取视频帧, 放入队列, 最后放入 None 表示结束
    """
    while True:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            await q.put(frame)

        cap.release()
        # 结束信号


async def print_frame_info_from_queue(q: asyncio.Queue) -> None:
    """
    消费者: 从队列取帧并打印信息; 收到 None 时结束
    """
    while True:
        frame = await q.get()
        print(f"Frame dtype: {frame.dtype}, shape: {frame.shape}")


async def main():
    q = asyncio.Queue(maxsize=10)

    # 启动生产者和消费者任务
    producer = asyncio.create_task(video_frames_queue(
        "/home/linslime/code/PyPersona/webrtc_media_streaming/sample_video.mp4", q
    ))
    consumer = asyncio.create_task(print_frame_info_from_queue(q))

    # 等待它们结束
    await asyncio.gather(producer, consumer)


if __name__ == "__main__":
    asyncio.run(main())
