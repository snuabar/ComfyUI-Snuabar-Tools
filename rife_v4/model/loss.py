import torch
import torch.nn as nn
import torch.nn.functional as F


class EPE(nn.Module):
    """端到端误差（End-Point-Error），仅训练时使用，推理不会调用。"""

    def __init__(self, ignore_mask=False):
        super(EPE, self).__init__()
        self.ignore_mask = ignore_mask

    def forward(self, flow, gt, loss_mask=None):
        if self.ignore_mask and loss_mask is not None:
            loss = (flow - gt).abs()
            return (loss * loss_mask).sum() / loss_mask.sum()
        return torch.mean((flow - gt).abs())


class SOBEL(nn.Module):
    """Sobel 边缘约束，仅训练时使用，推理不会调用。"""

    def __init__(self):
        super(SOBEL, self).__init__()
        kx = torch.tensor([[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]],
                          dtype=torch.float32).view(1, 1, 3, 3)
        ky = torch.tensor([[-1., -2., -1.], [0., 0., 0.], [1., 2., 1.]],
                          dtype=torch.float32).view(1, 1, 3, 3)
        self.register_buffer('kx', kx)
        self.register_buffer('ky', ky)

    def forward(self, x):
        # x: [B, 3, H, W] -> 灰度后求 Sobel 梯度
        g = x.mean(dim=1, keepdim=True)
        gx = F.conv2d(g, self.kx, padding=1)
        gy = F.conv2d(g, self.ky, padding=1)
        return torch.cat([gx, gy], dim=1)
