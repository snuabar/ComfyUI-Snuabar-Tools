import datetime
import os.path
from typing import Any

from comfy_api.latest import io
from my_server.ai_image_server import net_result, net_params


class NetParamNote(io.ComfyNode):

    def __init__(self):
        io.ComfyNode.__init__(self)

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
        if net_params is not None:
            return io.NodeOutput(
                net_params.prompt,
                net_params.seed,
                net_params.img_width,
                net_params.img_height
            )
        return io.NodeOutput()

    @classmethod
    def fingerprint_inputs(cls) -> Any:
        return f"{datetime.datetime.now()}"


class NetResultNote(io.ComfyNode):

    def __init__(self):
        io.ComfyNode.__init__(self)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="snuabar.net.result.note",
            display_name="Net Result",
            category="SnuabarTools",
            inputs=[
                io.String.Input(
                    id='output_file',
                    display_name='输出文件路径',
                ),
            ],
        )

    @classmethod
    def execute(cls, output_file) -> io.NodeOutput:
        if net_result is not None:
            net_result.status = 'success' if os.path.exists(output_file) else 'fail'
            net_result.file_path = output_file
        return io.NodeOutput()

    @classmethod
    def fingerprint_inputs(cls) -> Any:
        return f"{datetime.datetime.now()}"
