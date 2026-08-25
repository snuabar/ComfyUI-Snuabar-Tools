import os
import datetime
from typing import Any

from comfy_api.latest import io

from prompt_json_util import resolve_dir, ensure_json_ext, write_entry, DEFAULT_DIR


class SavePromptNode(io.ComfyNode):
    """
    保存 Prompt 到 array 类型的 JSON 文件。

    每条记录是一个 map：{"key": <键>, "value": <值>}
      - key  ：例如图片路径（可自由指定）
      - value：例如生成用的 prompt（支持多行，写入时由 JSON 自动转义换行）

    文件格式示例：
        [
          {"key": "img/001.png", "value": "a cat sitting on a chair"},
          {"key": "img/002.png", "value": "a dog running on the beach"}
        ]
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="snuabar.prompt.save",
            display_name="保存Prompt(JSON)",
            category="SnuabarTools",
            inputs=[
                io.String.Input(
                    id="key",
                    display_name="键 (Key)",
                    default="",
                    tooltip="每条记录的 key。通常连接到上游节点输出的图片路径，或手动输入任意标识；留空则存为空字符串。",
                ),
                io.String.Input(
                    id="value",
                    display_name="值 (Prompt)",
                    default="",
                    multiline=True,
                    tooltip="每条记录的 value（例如生成用的 prompt）。支持多行，写入时会自动转义换行。",
                ),
                io.String.Input(
                    id="directory",
                    display_name="文件夹目录",
                    default=DEFAULT_DIR,
                    optional=True,
                    tooltip="JSON 文件所在/输出目录（任意字符串）。默认指向 ComfyUI 的 output 目录；留空也回退到该目录。",
                ),
                io.String.Input(
                    id="filename",
                    display_name="文件名",
                    default="prompts",
                    optional=True,
                    tooltip="JSON 文件名（任意字符串，扩展名固定为 .json）。",
                ),
                io.Combo.Input(
                    id="write_mode",
                    options=["append", "overwrite"],
                    default="append",
                    display_name="写入类型",
                    tooltip="append=追加到数组末尾；overwrite=覆盖整个文件（数组仅保留本条）。",
                ),
            ],
            outputs=[
                io.String.Output(id="file_path", display_name="文件路径"),
                io.Int.Output(id="count", display_name="条目数"),
            ],
            is_output_node=True,  # 输出未连接时也始终执行（等价 V1 的 OUTPUT_NODE=True）
            description="将 key-value 以 {key,value} 形式保存到 array 类型的 JSON 文件中。",
        )

    @classmethod
    def execute(cls, key, value, directory, filename, write_mode):
        directory = resolve_dir(directory)
        filename = ensure_json_ext(filename)
        path = os.path.join(directory, filename)
        count = write_entry(path, key, value, write_mode)
        return io.NodeOutput(path, count)

    @classmethod
    def fingerprint_inputs(cls, **kwargs) -> Any:
        # 每次都返回不同的指纹，强制该节点每次都执行（不被 ComfyUI 的结果缓存跳过）。
        # 等价于 V1 的 IS_CHANGED = lambda: float("nan")。
        # 注意：必须在 execute 真的有副作用（写文件）时才这样用，否则会无谓地重复执行。
        return f"{datetime.datetime.now()}"
