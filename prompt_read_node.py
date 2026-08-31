import os

from comfy_api.latest import io
from prompt_json_util import (
    ensure_json_ext,
    read_array,
    DEFAULT_DIR,
)


class ReadPromptNode(io.ComfyNode):
    """从 array 类型的 JSON 文件读取指定索引的 map，分别输出其 key 与 value。

    文件格式：[{"key": ..., "value": ...}, ...]
     - value 中的换行在读取时由 JSON 自动恢复为真实换行（无需手动处理）。

    采用新版 comfy_api 实现。由用户直接指定 JSON 文件的完整路径
    （含文件名，默认指向 output 目录下的 prompts.json），索引选项决定读取哪一条。
    """

    @classmethod
    def define_schema(cls):
        # 默认直接指向 output 目录下的 prompts.json
        default_path = os.path.join(DEFAULT_DIR, "prompts.json")
        return io.Schema(
            node_id="snuabar.prompt.read",
            display_name="读取Prompt(JSON)",
            category="SnuabarTools",
            description="从 array 类型的 JSON 文件读取指定索引的 {key,value} 条目，分别输出 key 与 value。",
            inputs=[
                io.String.Input(
                    id="file_path",
                    display_name="JSON文件路径",
                    default=default_path,
                    optional=True,
                    tooltip="JSON 文件的完整路径（含文件名，例如 output/prompts.json）。默认指向 output 目录下的 prompts.json。",
                ),
                io.Int.Input(
                    id="index",
                    display_name="条目索引",
                    default=0,
                    min=0,
                    max=2147483647,
                    tooltip="要读取的数组下标（从 0 开始）。",
                ),
            ],
            outputs=[
                io.String.Output(id="key", display_name="键 (Key)"),
                io.String.Output(id="value", display_name="值 (Value, Prompt)"),
            ],
        )

    @classmethod
    def execute(cls, file_path, index):
        path = (file_path or "").strip()
        if not path:
            path = os.path.join(DEFAULT_DIR, "prompts.json")
        path = ensure_json_ext(path)

        if not os.path.isfile(path):
            raise FileNotFoundError(f"未找到 JSON 文件：{path}")

        data = read_array(path)
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"JSON 文件无有效条目：{path}")

        idx = int(index)
        if idx < 0 or idx >= len(data):
            raise IndexError(
                f"索引 {idx} 越界，文件共 {len(data)} 条（合法范围 0..{len(data) - 1}）。"
            )

        item = data[idx]
        if not isinstance(item, dict):
            raise ValueError(f"第 {idx} 条不是 map 类型：{item!r}")

        key = item.get("key", "")
        value = item.get("value", "")
        # JSON 已自动将转义的换行恢复为真实换行
        return io.NodeOutput(key, value)
