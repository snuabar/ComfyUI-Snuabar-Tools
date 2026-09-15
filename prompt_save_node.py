import os
import datetime
from typing import Any

from comfy_api.latest import io

from prompt_json_util import resolve_dir, ensure_json_ext, write_entry, DEFAULT_DIR


class SavePromptNode(io.ComfyNode):
    """
    保存 Prompt 到 array 类型的 JSON 文件。

    每条记录是一个 map：{"key": <键>, "value": <值1>, "value2": <值2>}
      - key   ：例如图片路径（可自由指定）
      - value ：例如生成用的 prompt（支持多行，写入时由 JSON 自动转义换行）
      - value2：第二个值（可选，缺省空串；旧记录无此字段时读取回空串）

    文件格式示例：
        [
          {"key": "img/001.png", "value": "a cat ...", "value2": "high quality"},
          {"key": "img/002.png", "value": "a dog ...", "value2": "low quality"}
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
                    tooltip="每条记录的第一个 value（例如生成用的 prompt）。支持多行，写入时会自动转义换行。",
                ),
                io.String.Input(
                    id="value2",
                    display_name="值2 (Prompt2)",
                    default="",
                    multiline=True,
                    optional=True,
                    tooltip="每条记录的第二个 value（可选）。同一个 key 下的第二个值，支持多行；留空则存为空字符串。",
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
                    # 必须设 optional=True —— 前端控件顺序的控制开关：
                    # comfy_api 会把本 inputs 列表拆成 required / optional 两段
                    # （见 comfy_api/latest/_io.py 的 create_input_dict_v1 /
                    # add_to_dict_v1），前端「required 段整体先渲染，optional 段
                    # 整体后渲染」，声明顺序只在同一段内生效。
                    # 不设的话它进 required 段，会被排到同在 optional 段的 value2
                    # 前面 → 控件顺序错乱。要让顺序 = 声明顺序，本列表里只应保留
                    # key / value 两个 required，其余全部 optional。
                    optional=True,
                    tooltip="append=追加到数组末尾；overwrite=覆盖整个文件（数组仅保留本条）。",
                ),
            ],
            outputs=[
                io.String.Output(id="file_path", display_name="文件路径"),
                io.Int.Output(id="count", display_name="条目数"),
            ],
            is_output_node=True,  # 输出未连接时也始终执行（等价 V1 的 OUTPUT_NODE=True）
            description="将 key 与两个 value 以 {key,value,value2} 形式保存到 array 类型的 JSON 文件中（value2 可选）。",
        )

    @classmethod
    def execute(cls, key, value, value2, directory, filename, write_mode):
        directory = resolve_dir(directory)
        filename = ensure_json_ext(filename)
        path = os.path.join(directory, filename)
        value2 = value2 or ""  # optional 端口未连线/未填写时可能传 None
        write_mode = write_mode or "append"  # 同上；None 会被 write_entry 当成 append
        count = write_entry(path, key, value, write_mode, value2=value2)
        return io.NodeOutput(path, count)

    @classmethod
    def fingerprint_inputs(cls, **kwargs) -> Any:
        # 每次都返回不同的指纹，强制该节点每次都执行（不被 ComfyUI 的结果缓存跳过）。
        # 等价于 V1 的 IS_CHANGED = lambda: float("nan")。
        # 注意：必须在 execute 真的有副作用（写文件）时才这样用，否则会无谓地重复执行。
        return f"{datetime.datetime.now()}"
