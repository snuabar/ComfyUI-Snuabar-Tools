import torch
import torch.nn.functional as F


def warp(x, flo):
    """
    根据光流 flo 将图像 x（第二帧）反向扭曲回第一帧坐标系。

    参数:
        x:   [B, C, H, W]  待扭曲的图像（第二帧）
        flo: [B, 2, H, W]  光流（x/y 两通道）
    返回:
        [B, C, H, W]  扭曲后的图像
    """
    B, C, H, W = x.size()

    # 构造归一化网格 [-1, 1]
    xx = torch.arange(0, W, device=x.device).view(1, 1, 1, W).repeat(B, 1, H, 1).float()
    yy = torch.arange(0, H, device=x.device).view(1, 1, H, 1).repeat(B, 1, 1, W).float()
    grid = torch.cat((xx, yy), 1)  # [B, 2, H, W]

    vgrid = grid + flo  # 加上光流偏移

    # 缩放到 [-1, 1] 供 grid_sample 使用
    vgrid[:, 0, :, :] = 2.0 * vgrid[:, 0, :, :] / max(W - 1, 1) - 1.0
    vgrid[:, 1, :, :] = 2.0 * vgrid[:, 1, :, :] / max(H - 1, 1) - 1.0

    vgrid = vgrid.permute(0, 2, 3, 1)  # [B, H, W, 2]
    output = F.grid_sample(x, vgrid, align_corners=True)
    return output
