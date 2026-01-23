# ai_image_server_thread.py
import hashlib
import json
import logging
import os.path
import socket
import threading
import urllib
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import uvicorn
import websockets
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import prompts

common_functions = {}

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server_address = "127.0.0.1:8188"


def queue_prompt(prompt, client_id, prompt_id):
    p = {"prompt": prompt, "client_id": client_id, "prompt_id": prompt_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return urllib.request.urlopen(req)


def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()


def get_history(prompt_id=None):
    if prompt_id is None:
        url = "http://{}/history".format(server_address)
    else:
        url = "http://{}/history/{}".format(server_address, prompt_id)
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


async def wait_finish(client_id, prompt_id):
    uri = f"ws://{server_address}/ws?clientId={client_id}"
    async with websockets.connect(uri) as websocket:
        # 监听 WebSocket 消息
        while True:
            message = await websocket.recv()

            if isinstance(message, str):
                data = json.loads(message)
                if data['type'] == 'executing':
                    if (data['data']['node'] is None and
                            data['data']['prompt_id'] == prompt_id):
                        break  # 执行完成
            else:
                # 二进制预览数据
                continue


async def get_images(client_id, prompt_id, prompt, seed, width, height):
    # 准备提示词
    prompt_json = prompts.t2i_wan22(prompt, seed, width, height)

    # 通过 HTTP 提交任务
    response = queue_prompt(prompt_json, client_id, prompt_id)
    if response and response.code == 200:
        response.read()

        await wait_finish(client_id, prompt_id)

        """提取图片数据"""
        output_images = get_output_images_from_history(prompt_id)
        return output_images
    return None


def get_output_images_from_history(prompt_id):
    # 获取结果
    history = get_history(prompt_id)[prompt_id]
    """提取图片数据"""
    output_images = {}
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                image_data = get_image(
                    image['filename'],
                    image['subfolder'],
                    image['type']
                )
                images_output.append(image_data)
        output_images[node_id] = images_output
    return output_images

def get_local_ip():
    """获取本机局域网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


class NetParams:
    def __init__(self):
        self.prompt = ''
        self.seed = 0
        self.img_width = 0
        self.img_height = 0

    def __eq__(self, other):
        return self.prompt == other.prompt and self.seed == other.seed and self.img_width == other.img_width and self.img_height == other.img_height


class NetResult:
    def __init__(self):
        self.file_path = None
        self.status = None

    def __eq__(self, other):
        return self.file_path == other.file_path


net_params = NetParams()
net_result = NetResult()


class AIImageServer:
    def __init__(self, host=None, port=0):
        """
        初始化AI图像生成服务器

        Args:
            host: 监听地址，默认0.0.0.0（所有接口）
            port: 监听端口，默认0（自动搜索）
        """
        self.local_ip = get_local_ip()
        self.host = host or self.local_ip
        self.port = port
        self.actual_port = port
        self.server = None
        self.thread = None
        self.is_running = False
        self.client_id = str(uuid.uuid4())
        self.prompt_id = None

        # 创建FastAPI应用
        self.app = FastAPI(
            title="AI图像生成服务器",
            version="1.0.0",
            description="接收Android请求，生成AI图像并返回"
        )

        # 配置CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 注册路由
        self.setup_routes()

    def find_available_port(self, start_port=8000, max_attempts=100):
        """查找可用的端口"""
        import socket

        for port in range(start_port, start_port + max_attempts):
            try:
                # 尝试绑定端口
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.host, port))
                sock.close()
                return port
            except OSError:
                continue
        raise OSError(f"在端口 {start_port}-{start_port + max_attempts - 1} 范围内找不到可用端口")

    # 请求模型
    class ImageRequest(BaseModel):
        prompt: str = Field(..., description="图像描述提示词", min_length=1, max_length=1000)
        seed: Optional[int] = Field(None, description="随机种子")
        img_width: int = Field(512, description="图像宽度", ge=64, le=4096)
        img_height: int = Field(512, description="图像高度", ge=64, le=4096)
        num_images: Optional[int] = Field(1, description="生成图像数量", ge=1, le=4)
        style: Optional[str] = Field("realistic", description="图像风格")
        negative_prompt: Optional[str] = Field(None, description="负面提示词")

    # 响应模型
    class ImageResponse(BaseModel):
        request_id: str
        status: str
        message: str
        image_url: Optional[str] = None
        image_paths: Optional[List[str]] = None
        parameters: dict
        created_at: str
        processing_time: Optional[float] = None

    def setup_routes(self):
        """设置API路由"""

        @self.app.get("/")
        async def root():
            """服务器根目录"""
            return {
                "message": "AI图像生成服务器",
                "status": "运行中",
                "endpoints": {
                    "POST /api/generate": "生成AI图像",
                    "GET /api/images/{request_id}": "获取生成的图像",
                    "GET /api/status/{request_id}": "检查生成状态",
                    "GET /api/stats": "服务器统计信息"
                },
                "server_info": {
                    "host": self.host,
                    "port": self.port,
                    "local_ip": self.local_ip
                },
                "timestamp": datetime.now().isoformat()
            }

        @self.app.post("/api/generate", response_model=self.ImageResponse)
        async def generate_image(request: AIImageServer.ImageRequest):
            """
            接收Android端的绘图请求
            """
            # 生成请求ID
            request_id = str(uuid.uuid4())[:8]
            start_time = datetime.now()

            logger.info(f"收到生成请求: {request_id}")
            logger.info(f"请求参数: {request.dict()}")

            # 验证参数
            if request.img_width * request.img_height > 4096 * 4096:  # 4096x4096
                raise HTTPException(
                    status_code=400,
                    detail=f"图像尺寸过大: {request.img_width}x{request.img_height}"
                )

            # 模拟AI图像生成
            try:
                await self.generate_ai_image(
                    prompt=request.prompt,
                    seed=request.seed or 0,
                    width=request.img_width,
                    height=request.img_height,
                    request_id=request_id
                )

                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()

                # 构建响应
                response = {
                    "request_id": request_id,
                    "status": net_result.status,
                    "message": "图像生成成功",
                    "image_url": f"http://{self.local_ip}:{self.port}/api/images/{request_id}",
                    "image_paths": net_result.file_path,
                    "parameters": request.dict(),
                    "created_at": start_time.isoformat(),
                    "processing_time": processing_time
                }

                logger.info(f"请求完成: {request_id}, 耗时: {processing_time:.2f}秒")

                return response

            except Exception as e:
                logger.error(f"图像生成失败: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"图像生成失败: {str(e)}"
                )

        @self.app.get("/api/images/{request_id}")
        async def get_image(request_id: str):
            """
            获取生成的图像
            """
            from fastapi.responses import FileResponse

            # 查找图像文件
            func = common_functions['get_today_output_directory']
            image_files = list(Path(func()).glob(f"*_{request_id}_*.png"))

            if not image_files:
                raise HTTPException(status_code=404, detail="图像未找到")

            image_file = image_files[0]

            return FileResponse(
                path=image_file,
                media_type="image/png",
                filename=f"generated_{request_id}.png"
            )

        @self.app.get("/api/status/{request_id}")
        async def check_status(request_id: str):
            """
            检查图像生成状态
            """
            return {
                "request_id": request_id,
                "status": "available",
                "message": "服务器在线",
                "timestamp": datetime.now().isoformat()
            }

        @self.app.get("/api/stats")
        async def get_stats():
            """
            获取服务器统计信息
            """
            func = common_functions['get_today_output_directory']
            output_dir = Path(func())
            image_files = list(output_dir.glob("*.png"))
            total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())

            return {
                "total_images": len(image_files),
                "storage_used_mb": total_size / (1024 * 1024),
                "server_status": "running" if self.is_running else "stopped",
                "uptime": self.get_uptime(),
                "server_address": f"http://{self.local_ip}:{self.port}"
            }

    async def generate_ai_image(self, prompt, seed, width, height, request_id):
        prompt_id = hashlib.sha256(f"{prompt}-{seed}-{width}-{height}".encode()).hexdigest()
        """图像生成"""
        if prompt_id != self.prompt_id:

            logger.info(f"开始生成图像: {request_id}")

            net_params.prompt = prompt
            net_params.seed = seed
            net_params.img_width = width
            net_params.img_height = height

            net_result.status = None
            net_result.file_path = None

            images = await get_images(self.client_id, prompt_id, prompt, seed, width, height)
            self.prompt_id = prompt_id
        else:
            # 获取结果
            """提取图片数据"""
            images = get_output_images_from_history(self.prompt_id)

        if images is not None and isinstance(images, dict):
            net_result.file_path = []
            no = 0
            for node_id in images:
                for image_data in images[node_id]:
                    from PIL import Image
                    import io
                    image = Image.open(io.BytesIO(image_data))

                    # 保存图像
                    filename = f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_{seed}_{request_id}_{no:05d}.png'
                    func = common_functions['get_today_output_directory']
                    filepath = os.path.join(func(), filename)

                    image.save(filepath, "PNG")
                    logger.info(f"图像已保存: {filepath}")
                    net_result.file_path.append(filepath)
                    net_result.status = "success"
                    no += 1
        else:
            net_result.status = "failed"

    def run_server(self):
        # 如果端口为0，自动查找可用端口
        if self.port == 0:
            self.actual_port = self.find_available_port(8000)  # 从8189开始找，避开ComfyUI的8188
        else:
            self.actual_port = self.port

        """运行服务器（在线程中调用）"""
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            loop="asyncio"
        )

        try:
            self.server = uvicorn.Server(config)
            self.is_running = True
            self.server.run()
        except OSError as e:
            if "10048" in str(e):  # Windows端口占用错误
                logger.error(f"端口 {self.actual_port} 被占用，尝试其他端口")
                if self.port != 0:
                    # 如果指定了端口但被占用，自动切换到其他端口
                    self.actual_port = self.find_available_port(self.actual_port + 1)
                    # 重新配置并运行
                    config = uvicorn.Config(
                        app=self.app,
                        host=self.host,
                        port=self.actual_port,
                        log_level="info",
                        loop="asyncio"
                    )
                    self.server = uvicorn.Server(config)
                    self.is_running = True
                    self.server.run()
            else:
                raise

    def start(self):
        """启动服务器（非阻塞）"""
        if self.is_running:
            logger.warning("服务器已经在运行")
            return

        self.thread = threading.Thread(
            target=self.run_server,
            name=f"AI-Server-Thread",
            daemon=True
        )

        self.thread.start()

        # 等待服务器启动
        import time
        for i in range(10):  # 最多等待10秒
            if self.is_running:
                logger.info(f"服务器已启动在 http://{self.local_ip}:{self.actual_port}")
                logger.info(f"本地访问: http://127.0.0.1:{self.actual_port}")
                return True
            time.sleep(1)

        logger.error("服务器启动超时")
        return False

    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.should_exit = True
            self.is_running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        logger.info("服务器已停止")

    def get_uptime(self):
        """获取服务器运行时间（简化版）"""
        if hasattr(self, 'start_time'):
            uptime = datetime.now() - self.start_time
            return str(uptime).split('.')[0]  # 去掉微秒部分
        return "0:00:00"

    def is_alive(self):
        """检查服务器是否在运行"""
        return self.is_running and self.thread and self.thread.is_alive()

    def get_server_url(self):
        """获取服务器URL"""
        return f"http://{self.local_ip}:{self.actual_port}"


# 创建服务器实例

def main():
    server = AIImageServer(port=8000)
    # 检查服务器状态
    if not server.is_alive():
        print("=" * 60)
        print("AI图像生成服务器")
        print("=" * 60)

        # 启动服务器（非阻塞）
        if server.start():
            print(f"✓ 服务器已启动")
            print(f"本地访问: http://127.0.0.1:8000")
            print(f"局域网访问: {server.get_server_url()}")
            print("=" * 60)
        else:
            print("✗ 服务器启动失败")


main()
# # 使用示例
# if __name__ == "__main__":
#
#     print("=" * 60)
#     print("AI图像生成服务器")
#     print("=" * 60)
#
#     # 启动服务器（非阻塞）
#     if server.start():
#         print(f"✓ 服务器已启动")
#         print(f"本地访问: http://127.0.0.1:8000")
#         print(f"局域网访问: {server.get_server_url()}")
#         print("=" * 60)
#         print("按 Ctrl+C 停止服务器")
#
#         try:
#             # 主线程继续执行其他任务
#             while True:
#                 # 这里可以添加其他逻辑
#                 time.sleep(1000)
#
#                 # 检查服务器状态
#                 if not server.is_alive():
#                     print("服务器已停止")
#                     break
#
#         except KeyboardInterrupt:
#             print("\n正在停止服务器...")
#             server.stop()
#     else:
#         print("✗ 服务器启动失败")
