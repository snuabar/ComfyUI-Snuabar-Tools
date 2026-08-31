import os
import threading

import torch
import torch.nn.functional as F

from comfy_api.latest import io

# ----------------------------------------------------------------------------
# 定位 rife_v4 权重目录（flownet.pkl 已随包内置，不再依赖外部 RIFEv4.22）
# ----------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_WEIGHTS_DIR = os.path.join(_HERE, "rife_v4", "weights")
_TRAIN_LOG = _WEIGHTS_DIR

# RIFE 模型为懒加载单例（避免 ComfyUI 启动时就把 ~39MB 权重和 torch 拉起来）
_model = None
_model_lock = threading.Lock()


def _load_model():
    global _model
    with _model_lock:
        if _model is not None:
            return _model
        # 从唯一命名包 rife_v4 加载模型定义，避免顶层 `model` 包名与
        # ComfyUI 其他自定义节点（同样带有 model/ 子包）发生 import 冲突。
        from rife_v4.network.RIFE_HDv3 import Model as RIFEModel
        m = RIFEModel()
        m.load_model(_TRAIN_LOG)  # 内部加载 train_log/flownet.pkl
        m.eval()
        _model = m
    return _model


def _round_to_multiple(value, multiple):
    """向上取整到 multiple 的倍数（至少保留 multiple）。"""
    return max(multiple, (value // multiple) * multiple)


class RIFEInterpolateNode(io.ComfyNode):
    """
    RIFE 视频插帧节点

    输入：一组按顺序排列的图像（ComfyUI 中一个 batch 张量即一个序列）
    输出：在相邻图像之间插入中间帧后的图像序列（同样为 batch 张量）

    说明：
    - RIFE 要求高/宽为 32 的倍数，节点内部会自动把尺寸对齐到 32 的倍数处理，
      默认再把结果缩回输入尺寸，避免改变输出分辨率。
    - 模型权重来自 RIFEv4.22/train_log/flownet.pkl，首次执行时加载并缓存。
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="snuabar.rife.interpolate",
            display_name="RIFE 视频插帧",
            category="SnuabarTools",
            inputs=[
                io.Image.Input(
                    id="images",
                    display_name="图像序列",
                    tooltip="按顺序输入的一组图像；在 ComfyUI 中一个 batch（多帧）即一个序列。",
                ),
                io.Int.Input(
                    id="insert_frames",
                    display_name="每两帧间插入帧数",
                    default=1,
                    min=1,
                    max=10,
                    tooltip="在每两张相邻图像之间插入的中间帧数量。",
                ),
                io.Float.Input(
                    id="scale",
                    display_name="处理缩放",
                    default=1.0,
                    min=0.25,
                    max=2.0,
                    tooltip=">1 时降低处理分辨率以节省显存/内存；1.0 为原生分辨率。",
                ),
                io.Boolean.Input(
                    id="resize_back",
                    display_name="还原尺寸",
                    default=True,
                    tooltip="插帧完成后是否把结果缩回输入尺寸（输入尺寸非 32 倍数时需要）。",
                ),
            ],
            outputs=[
                io.Image.Output(
                    id="images_out",
                    display_name="插帧后序列",
                ),
            ],
            description="使用 RIFEv4.22 在相邻图像间插入中间帧，输入/输出均为图像列表。",
        )

    @classmethod
    def execute(cls, images, insert_frames, scale, resize_back) -> io.NodeOutput:
        if images is None:
            raise ValueError("未提供图像序列")
        # images: [B, H, W, C] float32, 范围 0..1
        B, H, W, C = images.shape
        if B < 2:
            raise ValueError("视频插帧至少需要 2 帧图像")

        # 仅取前 3 通道（AI 生成图像通常为 RGB）
        if C > 3:
            images = images[:, :, :, :3]
            C = 3

        model = _load_model()
        dev = next(model.flownet.parameters()).device

        # 对齐到 32 的倍数（RIFE 网络要求）
        hr = _round_to_multiple(H, 32)
        wr = _round_to_multiple(W, 32)

        # [B, H, W, C] -> [B, C, H, W]，并搬到模型所在设备
        x = images.permute(0, 3, 1, 2).to(dev)
        if hr != H or wr != W:
            x = F.interpolate(x, size=(hr, wr), mode="bilinear", align_corners=False)

        insert = int(insert_frames)

        out_frames = []
        last = x[0:1].to("cpu")
        out_frames.append(last)
        for i in range(1, B):
            cur = x[i:i + 1]
            for k in range(1, insert + 1):
                timestep = k / (insert + 1)
                mid = model.inference(last.to(dev), cur, timestep=timestep, scale=float(scale))
                out_frames.append(mid.to("cpu"))
            out_frames.append(cur.to("cpu"))
            last = cur

        out_t = torch.cat(out_frames, dim=0)  # [B', C, hr, wr]
        if resize_back and (hr != H or wr != W):
            out_t = F.interpolate(out_t, size=(H, W), mode="bilinear", align_corners=False)

        # [B', C, H, W] -> [B', H, W, C]
        out_t = out_t.permute(0, 2, 3, 1).contiguous()
        return io.NodeOutput(out_t)
