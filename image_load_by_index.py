"""按索引从目录加载**单张**图片（惰性加载：只解码选中的那一张）。

为什么要自己写一个：
comfyui-mixlab-nodes 的 "Load Images From Path" 会先用 os.walk 把目录里
**每一张**图片全量解码成 float32 张量、全部驻留内存，然后才按 index 切片，
只留下 1 张、其余 121 张当场丢弃。
实测对本机 output/2026-09-10（122 张，约 1832×2288）：
全量解码 30.2 s、图像张量占用约 5.9 GB —— 而用户其实只要 index=1 这一张。

本节点的做法：
  1) os.walk 只列路径，**不解码**（122 个文件约 8 ms）
  2) 按文件名（自然序）或 mtime 排序（newest 时每文件一次 stat，约 21 ms）
  3) 只解码 index 指定的那一张（约 250 ms/张）
即：开销从「与目录下张数成正比」降为「与 1 张成正比」。
"""

import os
import re
import time
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageOps

from comfy_api.latest import io


IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp",
    ".gif", ".tiff", ".tif", ".jfif",
}


def natural_sort_key(name):
    """文件名自然排序：数字段按数值比较，保证 0002.png < 0010.png。"""
    return [int(p) if p.isdigit() else p.lower()
            for p in re.split(r"(\d+)", name)]


def list_image_files(directory):
    """列出目录下所有图片文件（递归）。只取路径，不解码。"""
    out = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                out.append(os.path.join(root, f))
    return out


def resolve_selected_path(directory, index, sort_by):
    """列出 -> 排序 -> 返回 (选中文件的路径, 目录内总张数)。不解码任何图片。"""
    directory = (directory or "").strip().strip('"')
    if not directory:
        raise ValueError("图片目录为空，请填写目录路径。")

    if os.path.isfile(directory):
        files = [directory]
    elif os.path.isdir(directory):
        files = list_image_files(directory)
    else:
        raise ValueError(f"路径不存在或不是有效目录：{directory}")

    if not files:
        raise ValueError(f"该目录下没有找到图片文件：{directory}")

    if sort_by == "newest":
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    else:  # file_name
        files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))

    idx = int(index or 0)
    if idx < 0 or idx >= len(files):
        raise IndexError(
            f"索引 {idx} 越界，该目录共 {len(files)} 张（合法范围 0..{len(files) - 1}）。"
        )
    return files[idx], len(files)


def load_one(path, white_bg=False):
    """解码单张图片 -> (image[1,H,W,3] float32, mask[H,W] float32)。

    与 mixlab 的 load_image 行为保持一致（含 exif 方向校正、alpha 遮罩），
    但只对调用方指定的这一张执行。
    """
    with Image.open(path) as raw:
        im = ImageOps.exif_transpose(raw)
        im.load()  # 确保像素已读入，退出 with 后仍可安全转换
        has_alpha = "A" in im.getbands()
        rgb = im.convert("RGB")
        alpha = im.getchannel("A") if has_alpha else None

    image = np.array(rgb).astype(np.float32) / 255.0
    image = torch.from_numpy(image)[None,]

    if alpha is not None:
        mask = np.array(alpha).astype(np.float32) / 255.0
        mask = 1.0 - torch.from_numpy(mask)
        if white_bg:
            nw = mask.unsqueeze(0).unsqueeze(-1).repeat(1, 1, 1, 3)
            image[nw == 1] = 1.0
    else:
        mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")

    return image, mask


class LoadImageByIndexNode(io.ComfyNode):
    """从目录按索引加载单张图片。

    与 mixlab 版本的关键差异：只解码 index 指定的那一张，
    不会把整个目录全量解码进内存。
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="snuabar.image.load_by_index",
            display_name="加载图像(按索引)",
            category="SnuabarTools",
            description="从目录按索引加载单张图片；只解码选中的那一张，不会全量解码整个目录。",
            # 注意：下面所有输入都保持 required（不设 optional）。
            # comfy_api 会把 inputs 拆成 required / optional 两段、前端让 required 段
            # 整体先渲染，混用会让控件顺序被打乱。全 required 时顺序 = 声明顺序。
            inputs=[
                io.String.Input(
                    id="directory",
                    display_name="图片目录",
                    default="",
                    tooltip="图片所在目录（递归查找子目录）。也可直接填单个图片文件的完整路径。",
                ),
                io.Int.Input(
                    id="index",
                    display_name="索引",
                    default=0,
                    min=0,
                    max=2147483647,
                    tooltip="要读取第几张（从 0 开始）。只解码这一张，其余不读。",
                ),
                io.Combo.Input(
                    id="sort_by",
                    options=["file_name", "newest"],
                    default="file_name",
                    display_name="排序方式",
                    tooltip="file_name=按文件名自然排序（0002 在 0010 前面）；newest=按修改时间从新到旧。",
                ),
                io.Combo.Input(
                    id="white_bg",
                    options=["disable", "enable"],
                    default="disable",
                    display_name="白色背景",
                    tooltip="enable=把透明区域填充为白色（仅对带 alpha 通道的图片有效）。",
                ),
            ],
            outputs=[
                io.Image.Output(id="image", display_name="图像"),
                io.Mask.Output(id="mask", display_name="遮罩"),
                io.String.Output(id="image_path", display_name="图片路径"),
                io.Int.Output(id="count", display_name="总张数"),
            ],
        )

    @classmethod
    def execute(cls, directory, index, sort_by, white_bg):
        path, total = resolve_selected_path(directory, index, sort_by)
        image, mask = load_one(path, white_bg == "enable")
        return io.NodeOutput(image, mask, path, total)

    @classmethod
    def fingerprint_inputs(cls, **kwargs) -> Any:
        """用「选中文件的路径 + mtime + 大小」做指纹。

        这样：内容没变 -> 命中缓存、不重复解码；文件被替换 / 新增导致选中的
        那张变了 -> 指纹变化 -> 真正重新解码。列表与 stat 的成本（约 30 ms）
        远低于解码（约 250 ms/张），所以这里做一次很划算。
        解析失败时退回「每次都变」的指纹，保证不会因为指纹报错卡住执行。
        """
        try:
            path, _total = resolve_selected_path(
                kwargs.get("directory"),
                kwargs.get("index", 0),
                kwargs.get("sort_by", "file_name"),
            )
            st = os.stat(path)
            return f"{path}|{st.st_mtime_ns}|{st.st_size}"
        except Exception:
            return f"{kwargs}|{time.time()}"
