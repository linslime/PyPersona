"""Minimal WebRTC media streamer.
启动示例：
    python server.py --video sample_video.mp4 --audio sample_audio.wav --port 8080
浏览器访问：http://localhost:8080
"""
import argparse
import asyncio
from pathlib import Path

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay

pcs = set()                  # 活跃的 PeerConnections
relay = MediaRelay()         # 多客户端复用同一解码源

# ---------------------- 路由处理 ---------------------- #
async def index(request: web.Request):
    """返回前端页面"""
    return web.FileResponse(Path(__file__).parent / "static" / "index.html")

async def offer(request: web.Request):
    """处理浏览器发送的 SDP offer，返回 answer"""
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # 创建 PeerConnection
    pc = RTCPeerConnection()
    pcs.add(pc)
    print("Created PC %s" % id(pc))

    # 当连接状态变化时清理
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("PC %s state %s" % (id(pc), pc.connectionState))
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            pcs.discard(pc)

    # 加载音视频文件
    video_src = MediaPlayer(request.app["video_path"], format=None).video
    audio_src = MediaPlayer(request.app["audio_path"], format=None).audio

    # 通过 relay 订阅（支持多客户端共享解码器）
    pc.addTrack(relay.subscribe(video_src))
    pc.addTrack(relay.subscribe(audio_src))

    # WebRTC SDP 交换
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    })

async def on_shutdown(app: web.Application):
    # 关闭所有活动连接
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

# ---------------------- 启动脚本 ---------------------- #

def main():
    parser = argparse.ArgumentParser(description="WebRTC media streamer (Python backend)")
    parser.add_argument("--video", required=True, help="Path to video file (e.g. mp4)")
    parser.add_argument("--audio", required=True, help="Path to audio file (e.g. wav/mp4)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    app = web.Application()
    app["video_path"] = str(Path(args.video).resolve())
    app["audio_path"] = str(Path(args.audio).resolve())

    app.router.add_get("/", index)
    app.router.add_static("/static/", path=str(Path(__file__).parent / "static"), name="static")
    app.router.add_post("/offer", offer)
    app.on_shutdown.append(on_shutdown)

    print(f"▶ Serving on http://{args.host}:{args.port}")
    web.run_app(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()