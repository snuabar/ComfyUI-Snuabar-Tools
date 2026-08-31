# rife_v4 —— RIFEv4.22 插帧模型的安全导入包
#
# 本包是 ComfyUI-Snuabar-Tools 的 RIFE 视频插帧节点 (rife_interpolate.py) 专用。
# 把 RIFEv4.22 的网络定义文件复制进带唯一命名空间的子包 (rife_v4.model / rife_v4.network)，
# 并将其内部的 `from model.xxx` / `from train_log.xxx` 改写为 `from rife_v4.xxx`，
# 从而避免顶层包名 `model` 与 ComfyUI 其他自定义节点（同样带有 model/ 子包）发生 import 冲突。
#
# RIFEv4.22 目录下的原始文件（train_log/*.py、flownet.pkl）不做任何修改，仅按路径读取权重。
