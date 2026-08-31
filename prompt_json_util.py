import os
import json

_HERE = os.path.dirname(os.path.abspath(__file__))


def default_directory():
    """默认存放目录 = ComfyUI 的 output 目录。

    通过 folder_paths.get_output_directory() 获取（与 ComfyUI 内置节点取输出目录
    的方式一致）；当该 API 不可用时（如离线/异常场景）回退到扩展内置的
    prompt_jsons 文件夹，保证模块仍能正常导入与运行。
    """
    try:
        import folder_paths
        out = folder_paths.get_output_directory()
        if out and os.path.isdir(out):
            return out
    except Exception:
        pass
    return os.path.join(_HERE, "prompt_jsons")


# 读写两个节点都以此作为「directory 留空」时的兜底位置，且与 directory 输入的
# 默认值保持一致（默认即 output 目录），保证开箱即用、互相衔接。
DEFAULT_DIR = default_directory()


def ensure_json_ext(name):
    """保证文件名以 .json 结尾（扩展名固定为 .json）。"""
    name = (name or "").strip()
    if not name:
        return "prompts.json"
    if not name.lower().endswith(".json"):
        name += ".json"
    return name


def resolve_dir(directory):
    """把目录参数解析为可用路径；为空时回退到默认目录。"""
    directory = (directory or "").strip()
    if not directory:
        return DEFAULT_DIR
    return directory


def list_json_files(directory):
    """列出指定目录下所有 .json 文件（含扩展名，已排序）。目录不存在时返回空列表。"""
    directory = resolve_dir(directory)
    if not os.path.isdir(directory):
        return []
    files = []
    for f in os.listdir(directory):
        full = os.path.join(directory, f)
        if f.lower().endswith(".json") and os.path.isfile(full):
            files.append(f)
    files.sort()
    return files


def read_array(path):
    """读取 JSON 文件并尽可能返回 array。

    - 文件不存在 -> []
    - 内容为 list -> 原样返回
    - 内容为单个 object -> 包成 [object]（容错）
    - 解析失败 -> []
    """
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, list):
        return data
    return [data]


def write_entry(path, key, value, mode):
    """向 array 类型 JSON 写入一条 {key, value} 记录。

    mode:
      - "overwrite": 覆盖整个文件（结果数组仅含本条）
      - "append"   : 追加到数组末尾

    返回写入后数组的条目数。
    换行在 json.dump 时会自动转义为 \\n，无需手动处理。
    """
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)

    if mode == "overwrite":
        data = []
    else:  # append
        data = read_array(path)
        if not isinstance(data, list):
            data = [data]

    data.append({"key": key, "value": value})

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(data)
