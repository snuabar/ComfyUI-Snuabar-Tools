import datetime
import sys
import os
import time
from typing import Any

from comfy_api.latest import io
from my_server.ai_image_server import server, NetParams


class NetParamNote(io.ComfyNode):

    param: NetParams = None

    def __init__(self):
        io.ComfyNode.__init__(self)
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

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="snuabar.net.param.note",
            display_name="Net Params",
            category="SnuabarTools",
            outputs=[
                io.String.Output(
                    id='prompt',
                    display_name='正向提示词',
                ),
                io.Int.Output(
                    id='seed',
                    display_name='种子',
                ),
                io.Int.Output(
                    id='width',
                    display_name='图像宽度',
                ),
                io.Int.Output(
                    id='height',
                    display_name='图像高度',
                ),
            ],
            description="用于格式化字符串的工具节点。",
        )

    @classmethod
    def execute(cls) -> io.NodeOutput:
        if server:
            return io.NodeOutput(server.params.prompt, server.params.seed, server.params.img_width, server.params.img_height)
        return io.NodeOutput()

    @classmethod
    def fingerprint_inputs(cls) -> Any:
        return server.params