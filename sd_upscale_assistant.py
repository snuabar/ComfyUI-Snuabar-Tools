import datetime
from typing import Any

from comfy_api.latest import io


class SDUpscaleAssistant(io.ComfyNode):

    def __init__(self):
        super().__init__()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="snuabar.sd.upscale.assistant",
            display_name="SD放大助手 ",
            category="SnuabarTools",
            inputs=[
                io.Int.Input(
                    id='width',
                    display_name='图像宽'
                ),
                io.Int.Input(
                    id='height',
                    display_name='图像高'
                ),
                io.Float.Input(
                    id='upscale_factor',
                    display_name='放大系数'
                )
            ],
            outputs=[
                io.Float.Output(
                    id='out_upscale_factor',
                    display_name='放大系数'
                ),
                io.Int.Output(
                    id='tile_width',
                    display_name='分块宽度'
                ),
                io.Int.Output(
                    id='tile_height',
                    display_name='分块高度'
                ),
                io.Int.Output(
                    id='mask_blur',
                    display_name='模糊'
                ),
                io.Int.Output(
                    id='tile_padding',
                    display_name='分块分区'
                ),
            ]
        )

    @classmethod
    def execute(cls, width, height, upscale_factor) -> io.NodeOutput:
        default_mask_blur = 8
        default_tile_padding = 32
        mask_blur = default_mask_blur * upscale_factor
        tile_padding = default_tile_padding * upscale_factor
        tile_width = (width * upscale_factor) // 2
        tile_height = (height * upscale_factor) // 2
        return io.NodeOutput(upscale_factor, int(tile_width), int(tile_height), int(mask_blur), int(tile_padding))

    @classmethod
    def fingerprint_inputs(cls, width, height, upscale_factor) -> Any:
        return f"{datetime.datetime.now()}"
