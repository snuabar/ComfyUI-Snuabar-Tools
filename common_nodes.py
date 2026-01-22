import os

from comfy_api.latest import io
from comfy_api.latest._io import NodeOutput


class AbsPathNode(io.ComfyNode):

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="snuabar.abs.path.note",
            display_name="绝对路径",
            category="SnuabarTools",
            inputs=[
                io.String.Input(
                    id='input_path',
                    display_name='输入',
                ),
                io.Boolean.Input(
                    id='no_exist_ok',
                    default=False,
                    display_name='不存在也行'
                )
            ],
            outputs=[
                io.String.Output(
                    id='output_path',
                    display_name='输出'
                )
            ]
        )

    @classmethod
    def execute(cls, input_path, no_exist_ok) -> NodeOutput:
        abs_path = os.path.abspath(input_path)
        if not os.path.exists(abs_path):
            abs_path = os.path.normpath(input_path)
            if not os.path.exists(abs_path) and not no_exist_ok:
                raise ValueError(f"Directory {abs_path} does not exist")
        return NodeOutput(abs_path)
    #
    # @classmethod
    # def fingerprint_inputs(cls, input_path, ) -> Any:
    #     return input_path
