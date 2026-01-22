import datetime
from typing import Any

import global_vars
from comfy_api.latest import io


class ImageAutoSelectNote(io.ComfyNode):

    def __init__(self):
        super().__init__()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="snuabar.image.auto.selector",
            display_name="自动选择图像",
            category="SnuabarTools",
            inputs=[
                io.Image.Input(
                    id='image0',
                    display_name='图像1',
                    optional=True,
                ),
                io.Image.Input(
                    id='image1',
                    display_name='图像2',
                    optional=True,
                ),
                io.Int.Input(
                    id='current_image',
                    display_name='当前图像',
                    max=2,
                    min=1,
                    default=1,
                )
            ],
            outputs=[
                io.Image.Output(
                    id='image_out',
                    display_name='输出图像'
                )
            ]
        )

    @classmethod
    def execute(cls, image0=None, image1=None, current_image=1, *arg, **kwargs) -> io.NodeOutput:
        if current_image == 1 and image0:
            return io.NodeOutput(image0)
        elif current_image == 2 and image1:
            return io.NodeOutput(image1)
        out_img = image0 if image0 else image1
        return io.NodeOutput(out_img)

    @classmethod
    def fingerprint_inputs(cls, image0=None, image1=None, current_image=1, *arg, **kwargs) -> Any:
        return f"{datetime.datetime.now()}"

class ImageTempNote(io.ComfyNode):

    def __init__(self):
        super().__init__()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="snuabar.image.temp",
            display_name="临时图像",
            category="SnuabarTools",
            inputs=[
                io.Image.Input(
                    id='image',
                    display_name='图像',
                    optional=True,
                ),
            ],
            outputs=[
                io.Image.Output(
                    id='image_out',
                    display_name='输出图像'
                ),
                io.Boolean.Output(
                    id='is_none',
                    display_name='is None'
                ),
            ]
        )

    @classmethod
    def execute(cls, image=None) -> io.NodeOutput:
        if not image is None:
            global_vars.temp_image = image
        else:
            image = global_vars.temp_image
        return io.NodeOutput(image, image is None)

    @classmethod
    def fingerprint_inputs(cls, image=None) -> Any:
        return f"{datetime.datetime.now()}"
