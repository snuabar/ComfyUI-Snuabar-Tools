# ai_image_server_thread.py
import hashlib
import http.client
import json
import logging
import os.path
import socket
import threading
import urllib
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import folder_paths
import workflows as wf
from comfy_execution.jobs import JobStatus

common_functions = {}

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server_address = "127.0.0.1:8188"


def _get_datetime_now_utc():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def generate_prompt_id(*args):
    inputs = []
    for value in args:
        inputs.append(f'-{value}')
    inputs.append('-')

    inputs_str = "".join(inputs)
    prompt_id = hashlib.sha256(inputs_str.encode()).hexdigest()

    return prompt_id


def _get_request_id(prompt_id):
    return prompt_id[:8]


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


def get_jobs(prompt_id=None):
    if prompt_id is None:
        url = f"http://{server_address}/api/jobs"
    else:
        url = f"http://{server_address}/api/jobs/{prompt_id}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


async def get_output_images_from_history(prompt_id, history=None):
    # 获取结果
    if history is None:
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
    return output_images, history


async def get_output_video_from_history(prompt_id, history=None):
    """提取视频数据"""
    # 获取结果
    if history is None:
        history = get_history(prompt_id)[prompt_id]
    output_videos = {}
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                videos.append(video)
        output_videos[node_id] = videos
    return output_videos, history


def get_local_ips():
    """获取本机所有局域网IP地址（IPv4和IPv6）"""
    local_ips = {
        "ipv4": [],
        "ipv6": []
    }

    # 尝试获取所有网络接口的地址信息
    try:
        # 获取主机名
        hostname = socket.gethostname()

        # 获取所有IP地址信息
        addrinfo_list = socket.getaddrinfo(hostname, None)

        for addr_info in addrinfo_list:
            family = addr_info[0]
            address = addr_info[4][0]

            # 过滤回环地址和链路本地地址
            if address.startswith("127.") or address == "::1":
                continue

            # 根据地址族分类
            if family == socket.AF_INET:  # IPv4
                if address not in local_ips["ipv4"]:
                    local_ips["ipv4"].append(address)
            elif family == socket.AF_INET6:  # IPv6
                # 过滤IPv6链路本地地址（fe80::/10）
                if address.startswith("fe80:"):
                    continue
                if address not in local_ips["ipv6"]:
                    local_ips["ipv6"].append(address)

    except Exception as e:
        print(f"获取IP地址时出错: {e}")
        local_ips["ipv4"].append("127.0.0.1")
        local_ips["ipv6"].append("::1")

    return local_ips


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


def _get_job_status(job):
    if job is not None and isinstance(job, dict) and 'status' in job:
        return job['status']
    return ''


def _get_output_video_from_job(job):
    output_videos = {}
    for node_id in job['outputs']:
        node_output = job['outputs'][node_id]
        videos = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                videos.append(video)
        output_videos[node_id] = videos
    return output_videos


def _get_output_images_from_job(job):
    """提取图片数据"""
    output_images = {}
    for node_id in job['outputs']:
        node_output = job['outputs'][node_id]
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


class AIImageServer:
    def __init__(self, host=None, port=0, local_ip: str = None, is_v6: bool = False):
        """
        初始化AI图像生成服务器

        Args:
            host: 监听地址，默认0.0.0.0（所有接口）
            port: 监听端口，默认0（自动搜索）
        """
        self.local_ip = local_ip
        self.is_v6 = is_v6
        self.host = host or self.local_ip
        self.port = port
        self.actual_port = port
        self.server = None
        self.thread = None
        self.is_running = False
        self.client_id = str(uuid.uuid4())
        self.prompt_id = None
        self.running_request: dict[str, AIImageServer.QueueRequest] = {}

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
    class QueueRequest(BaseModel):
        workflow: str = Field(..., description="工作流", min_length=1, max_length=1000)
        model: str = Field(None, description="模型", min_length=1, max_length=1000)
        prompt: str = Field(..., description="图像描述提示词", min_length=1, max_length=1000)
        seed: Optional[int] = Field(None, description="随机种子")
        img_width: int = Field(512, description="图像宽度", ge=64, le=4096)
        img_height: int = Field(512, description="图像高度", ge=64, le=4096)
        num_images: Optional[int] = Field(1, description="生成图像数量", ge=1, le=4)
        style: Optional[str] = Field("realistic", description="图像风格")
        negative_prompt: Optional[str] = Field(None, description="负面提示词")
        upscale_factor: Optional[float] = Field(None, description="放大系数")
        step: Optional[int] = Field(None, description="步数")
        cfg: Optional[float] = Field(None, description="相关性CFG")
        seconds: int = Field(0, description="视频时长（秒）")

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

    class InterruptRequest(BaseModel):
        prompt_id: str = Field(None, description='ID')

    def setup_routes(self):
        """设置API路由"""

        @self.app.get("/")
        async def root():
            """服务器根目录"""
            return {
                "message": "AI图像生成服务器",
                "status": "运行中",
                "endpoints": {
                    "GET /api/workflows": "获取工作流",
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

        @self.app.get("/api/workflows")
        async def workflows():
            wf.load_workflows()
            return {
                "workflows": wf.workflow_list
            }

        @self.app.get("/api/models")
        async def model_type_list():
            model_types = list(folder_paths.folder_names_and_paths.keys())
            return {
                "model_types": model_types
            }

        @self.app.get("/api/models/{model_type}")
        async def model_list(model_type: str):
            files = folder_paths.get_filename_list(model_type)
            return {
                "models": files
            }

        @self.app.post("/api/enqueue")
        async def enqueue(request: AIImageServer.QueueRequest):
            # 创建参数ID
            prompt_id = generate_prompt_id(
                request.workflow,
                request.model,
                request.prompt,
                request.seed,
                request.img_width,
                request.img_height,
                request.upscale_factor,
                request.step,
                request.cfg,
                request.seconds,
            )
            # 通过参数ID获取请求ID
            request_id = _get_request_id(prompt_id)
            # 查找图像文件
            _files, is_video = find_output_file(request_id)
            if _files and len(_files) > 0:
                self.running_request[prompt_id] = request
                return {
                    "prompt_id": prompt_id,
                    "code": http.client.OK,
                    "message": 'success',
                    "parameters": request.model_dump(),
                    "utc_timestamp": f"{_get_datetime_now_utc()}",
                    "file_exists": True,
                }

            if prompt_id in self.running_request:
                return {
                    "prompt_id": prompt_id,
                    "code": http.client.CONFLICT,
                    "message": f"request is already in queue.",
                    "parameters": request.model_dump(),
                    "utc_timestamp": f"{_get_datetime_now_utc()}",
                }

            self.prompt_id = prompt_id

            # 准备提示词
            if len(wf.workflow_func_map) == 0:
                wf.load_workflows()
            workflow_prompt_func = wf.workflow_func_map[request.workflow]
            if workflow_prompt_func is None:
                return {
                    "prompt_id": self.prompt_id,
                    "code": http.client.NOT_FOUND,
                    "message": f"workflow {request.workflow} not found",
                    "parameters": request.model_dump(),
                    "utc_timestamp": f"{_get_datetime_now_utc()}",
                }

            prompt_json = workflow_prompt_func(
                model=request.model,
                prompt_p=request.prompt,
                seed=request.seed,
                width=request.img_width,
                height=request.img_height,
                step=request.step,
                cfg=request.cfg,
                upscale_factor=request.upscale_factor,
                seconds=request.seconds,
            )

            # 通过 HTTP 提交任务
            response = queue_prompt(prompt_json, self.client_id, prompt_id)
            if response is not None:
                if response.code == 200:
                    self.running_request[prompt_id] = request
                # response_body = response.read()
                return {
                    "prompt_id": self.prompt_id,
                    "code": response.code,
                    "message": response.msg,
                    "parameters": request.model_dump(),
                    "utc_timestamp": f"{_get_datetime_now_utc()}",
                }

            return {
                "prompt_id": self.prompt_id,
                "code": http.client.INTERNAL_SERVER_ERROR,
                "message": f"internal server error",
                "parameters": request.model_dump(),
                "utc_timestamp": f"{_get_datetime_now_utc()}",
            }

        @self.app.post("/api/interrupt")
        async def interrupt(request: AIImageServer.InterruptRequest):
            data = json.dumps(request.model_dump()).encode('utf-8')
            req = urllib.request.Request(f"http://{server_address}/interrupt", data=data)
            with urllib.request.urlopen(req) as response:
                if response.code == 200 and request.prompt_id in self.running_request:
                    self.running_request.pop(request.prompt_id)
                return {
                    "status_code": response.code,
                    "message": response.msg,
                    "prompt_id": request.prompt_id,
                }

        def find_output_file(request_id: str):
            # 查找图像文件
            func = common_functions['get_today_output_directory']
            files = list(Path(func()).glob(f"*_{request_id}_*.png"))
            if files is None or len(files) == 0:
                files = list(Path(func()).glob(f"*_{request_id}_*.mp4"))
                if files is not None and len(files) > 0:
                    return files, True
            return files, False

        @self.app.get("/api/download/{prompt_id}")
        async def _download(prompt_id: str):
            """
            获取生成的图像
            """
            from fastapi.responses import FileResponse

            request_id = _get_request_id(prompt_id)
            # 查找图像文件
            output_files, is_video = find_output_file(request_id)

            if not output_files:
                raise HTTPException(status_code=404, detail="文件未找到")

            output_file = output_files[0]
            file_name = os.path.basename(output_file)
            return FileResponse(
                path=output_file,
                media_type="video/mp4" if is_video else "image/png",
                filename=file_name
            )

        @self.app.get("/api/images/{prompt_id}")
        async def get_output_files(prompt_id: str):
            """
            获取生成的图像
            """

            request_id = _get_request_id(prompt_id)

            if not prompt_id in self.running_request:
                file_names, is_video = find_output_file(request_id)
                if file_names is not None and len(file_names) > 0:
                    return {
                        'prompt_id': prompt_id,
                        'code': http.client.OK,
                        'message': f"OK",
                        'status': JobStatus.COMPLETED,
                        'media_type': "video/mp4" if is_video else "image/png",
                        'filename': file_names[0].name,
                        "utc_timestamp": f"{_get_datetime_now_utc()}",
                    }
                return {
                    'prompt_id': prompt_id,
                    "code": http.client.NOT_FOUND,
                    "message": f"prompt {prompt_id} not found",
                    'status': JobStatus.FAILED,
                    "utc_timestamp": f"{_get_datetime_now_utc()}",
                }

            _request = self.running_request[prompt_id]

            job = get_jobs(prompt_id)
            _status = _get_job_status(job)
            if _status == JobStatus.COMPLETED:
                # history = get_history(prompt_id)
                # if history is not None and len(history) > 0:
                end_time = f"{_get_datetime_now_utc()}"
                if 'execution_end_time' in job:
                    end_time = f"{job['execution_end_time']}"
                filename = ''
                filepath = ''
                is_video = _request.seconds > 0
                if is_video:
                    # videos, _ = await get_output_video_from_history(prompt_id, history=history[prompt_id])
                    videos = _get_output_video_from_job(job)
                    if videos is not None and isinstance(videos, dict):
                        no = 0
                        for node_id in videos:
                            for video_data in videos[node_id]:
                                # 转移视频
                                ori_file = video_data['fullpath']
                                filename_no_ext = f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_{_request.seed}_{request_id}_{no:05d}'
                                filename = f'{filename_no_ext}.mp4'
                                func = common_functions['get_today_output_directory']
                                filepath = os.path.join(func(), filename)
                                os.rename(ori_file, filepath)
                                no += 1

                                try:
                                    # 转移尾帧图像
                                    ori_file_without_ext = os.path.splitext(ori_file)[0]
                                    last_frame = ori_file_without_ext + '_.png'
                                    if os.path.exists(last_frame):
                                        dest_last_frame = os.path.join(func(), filename_no_ext + '_[-1].png')
                                        os.rename(last_frame, dest_last_frame)
                                except Exception as e:
                                    print(f"首帧图像清理失败：{e}")

                                try:
                                    # 清理自动生成的首帧图像
                                    ori_file_without_ext = os.path.splitext(ori_file)[0]
                                    first_frame = ori_file_without_ext + '.png'
                                    if os.path.exists(first_frame):
                                        os.remove(first_frame)
                                except Exception as e:
                                    print(f"首帧图像清理失败：{e}")
                else:
                    # images, _ = await get_output_images_from_history(prompt_id, history=history[prompt_id])
                    images = _get_output_images_from_job(job)
                    if images is not None and isinstance(images, dict):
                        no = 0
                        for node_id in images:
                            for image_data in images[node_id]:
                                from PIL import Image
                                import io
                                image = Image.open(io.BytesIO(image_data))

                                # 保存图像
                                filename = f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_{_request.seed}_{request_id}_{no:05d}.png'
                                func = common_functions['get_today_output_directory']
                                filepath = os.path.join(func(), filename)

                                image.save(filepath, "PNG")
                                logger.info(f"图像已保存: {filepath}")
                                no += 1

                if os.path.exists(filepath) and os.path.isfile(filepath):
                    self.running_request.pop(prompt_id)
                    return {
                        'prompt_id': prompt_id,
                        'code': http.client.OK,
                        'message': f"OK",
                        'status': _status,
                        'media_type': "video/mp4" if is_video else "image/png",
                        'filename': filename,
                        "utc_timestamp": end_time,
                    }
            elif _status == JobStatus.PENDING:
                end_time = f"{_get_datetime_now_utc()}"
                if 'execution_end_time' in job:
                    end_time = f"{job['execution_end_time']}"
                return {
                    'prompt_id': prompt_id,
                    'code': http.client.ACCEPTED,
                    'message': "pending",
                    'status': _status,
                    "utc_timestamp": end_time,
                }
            elif _status == JobStatus.FAILED:
                end_time = f"{_get_datetime_now_utc()}"
                error_msg = f"unknown failure."
                if 'execution_error' in job:
                    error_msg = job['execution_error']
                if 'execution_end_time' in job:
                    end_time = f"{job['execution_end_time']}"
                return {
                    'prompt_id': prompt_id,
                    'code': http.client.EXPECTATION_FAILED,
                    'message': error_msg,
                    'status': _status,
                    "utc_timestamp": end_time,
                }

            return {
                'prompt_id': prompt_id,
                'code': http.client.NO_CONTENT,
                'message': f"processing",
                'status': _status,
                "utc_timestamp": f"{_get_datetime_now_utc()}",
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
                "server_address": f"http://[{self.local_ip}]:{self.port}" if self.is_v6 else f"http://{self.local_ip}:{self.port}"
            }

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
                if self.is_v6:
                    logger.info(f"服务器已启动在 http://[{self.local_ip}]:{self.actual_port}")
                else:
                    logger.info(f"服务器已启动在 http://{self.local_ip}:{self.actual_port}")
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
        if self.is_v6:
            return f"http://[{self.local_ip}]:{self.actual_port}"
        return f"http://{self.local_ip}:{self.actual_port}"


# 创建服务器实例

def main():
    """获取本机主要局域网IP（优先返回IPv4）"""

    ip = "127.0.0.1"
    is_v6 = False
    ips = get_local_ips()
    import sys
    if '--listen' in sys.argv:
        idx = sys.argv.index('--listen')
        if idx != -1:
            ip_addr = sys.argv[idx + 1]
            if ips["ipv4"] and ip_addr in ips["ipv4"]:
                ip = ip_addr
            elif ips["ipv6"] and ip_addr in ips["ipv6"]:
                ip = ip_addr
                is_v6 = True
            else:
                logger.error(f"找不到监听地址：{ip_addr}, 默认使用本地地址：127.0.0.1")

    server = AIImageServer(port=8000, local_ip=ip, is_v6=is_v6)
    # 检查服务器状态
    if not server.is_alive():
        print("=" * 60)
        print("AI图像生成服务器")
        print("=" * 60)

        # 启动服务器（非阻塞）
        if server.start():
            print(f"✓ 服务器已启动")
            print(f"访问地址: {server.get_server_url()}")
            print("=" * 60)

            global server_address
            if is_v6:
                server_address = f"[{server.local_ip}]:8188"
            else:
                server_address = f"{server.local_ip}:8188"
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
