import os
import threading

from comfy_api.latest import io
# Hidden 不在 io 的公开 __all__ 里（io = _io_public，仅 from ._io import *），
# 只能通过私有模块拿到。声明 hidden=[Hidden.unique_id] 后，框架才会往
# hidden_inputs 填 UNIQUE_ID，cls.hidden.unique_id 才会非 None（否则永远 None）。
from comfy_api.latest._io import Hidden

from prompt_json_util import (
    ensure_json_ext,
    read_array,
    DEFAULT_DIR,
)

# 按节点 unique_id 缓存「上次 execute 解析出的真实 JSON 路径」。
# 用途：fingerprint_inputs 阶段，若 file_path 是「连线输入」，框架传入的是 None
# （execution_list=None 导致 mark_missing），此时用上次 execute 缓存的真实路径
# 去 stat 文件，才能正确检测外部改动。widget 直填的路径会优先于缓存使用。
_RESOLVED_PATH_CACHE: dict[str, str] = {}
_CACHE_LOCK = threading.Lock()


def _get_uid(cls) -> str | None:
    """从 new-API 注入的 hidden 里取节点唯一 ID（多实例隔离用）。"""
    hidden = getattr(cls, "hidden", None)
    if hidden is None:
        return None
    return getattr(hidden, "unique_id", None)


class ReadPromptNode(io.ComfyNode):
    """从 array 类型的 JSON 文件读取指定索引的 map，分别输出其 key、value 与 value2。

    文件格式：[{"key": ..., "value": ..., "value2": ...}, ...]
     - value / value2 中的换行在读取时由 JSON 自动恢复为真实换行（无需手动处理）。
     - 旧记录没有 value2 字段时，输出空串（向后兼容，不会报错）。

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
            description="从 array 类型的 JSON 文件读取指定索引的 {key,value,value2} 条目，分别输出 key、value 与 value2。",
            hidden=[Hidden.unique_id],  # 声明后框架注入 UNIQUE_ID，cls.hidden.unique_id 才非 None
            inputs=[
                # 注意：本节点两个输入都保持 required（不设 optional）。
                # comfy_api 会把 inputs 拆成 required / optional 两段，前端让 required
                # 段整体先渲染，所以「两个都 required」时才会严格按声明顺序显示
                # （JSON文件路径 → 条目索引）。若只给其中一个设 optional，它就会被
                # 挪到另一段，控件顺序反而会乱。成因详见 prompt_save_node.py 的说明。
                io.String.Input(
                    id="file_path",
                    display_name="JSON文件路径",
                    default=default_path,
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
                io.String.Output(id="value2", display_name="值2 (Value2)"),
            ],
        )

    @classmethod
    def execute(cls, file_path, index):
        path = cls._resolve_path(file_path)

        if not os.path.isfile(path):
            raise FileNotFoundError(f"未找到 JSON 文件：{path}")

        # 缓存解析出的真实路径，供 fingerprint_inputs 在「连线输入」场景下使用
        uid = _get_uid(cls)
        if uid is not None:
            with _CACHE_LOCK:
                _RESOLVED_PATH_CACHE[uid] = path

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
        # 旧记录没有 value2 字段，这里回退为空串（向后兼容）
        value2 = item.get("value2", "")
        # JSON 已自动将转义的换行恢复为真实换行
        return io.NodeOutput(key, value, value2)

    @classmethod
    def fingerprint_inputs(cls, **kwargs) -> str:
        """让节点在「入参不变、但 JSON 文件被外部修改」时也重新读取。

        等价于 V1 的 IS_CHANGED：框架会比较本次返回值与上次是否相同，
        相同则跳过执行（直接复用缓存），不同才会重新跑 execute。

        把「文件路径 + 修改时间(mtime_ns) + 大小(size)」编进指纹：
          - JSON 文件被改（mtime/size 变化）→ 指纹变 → 重新读取；
          - 文件没动 → 指纹不变 → 不重跑（保持原缓存，省一次磁盘读）。

        关键坑：file_path 若是从别的节点「连线」过来的，fingerprint 阶段
        （execution_list=None）会拿到 None，无法直接 stat。此时改用 execute
        上次缓存的真实路径；若连缓存都没有（首跑），再退回默认路径。
        widget 直填的路径则优先直接使用，最准确。
        """
        path = cls._resolve_fingerprint_path(**kwargs)
        if path and os.path.isfile(path):
            st = os.stat(path)
            return f"{path}|{st.st_mtime_ns}|{st.st_size}"
        # 文件不存在：返回稳定指纹（不要含时间相关值，否则会每次都重跑）
        return path or "<no-path>"

    @classmethod
    def _resolve_path(cls, file_path):
        """execute 用：解析成最终要读取的 JSON 路径（含默认值回退）。"""
        path = (file_path or "").strip()
        if not path:
            path = os.path.join(DEFAULT_DIR, "prompts.json")
        return ensure_json_ext(path)

    @classmethod
    def _resolve_fingerprint_path(cls, **kwargs):
        """fingerprint 用：决定本次要 stat 哪个文件。

        优先级：1) 传入的 file_path（widget 直填）→ 2) execute 缓存的真实路径
        （连线输入场景）→ 3) 默认路径。
        """
        fp = (kwargs.get("file_path") or "").strip()
        if fp:
            return ensure_json_ext(fp)
        uid = _get_uid(cls)
        if uid is not None:
            with _CACHE_LOCK:
                cached = _RESOLVED_PATH_CACHE.get(uid)
            if cached:
                return cached
        return ensure_json_ext(os.path.join(DEFAULT_DIR, "prompts.json"))
