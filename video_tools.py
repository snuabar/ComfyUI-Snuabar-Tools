import os
import subprocess
import sys
from pathlib import Path
from typing import Any
import datetime
import common_fun

from comfy_api.latest import io


def find_ffmpeg():
    """查找FFmpeg可执行文件"""
    # 检查环境变量PATH
    import shutil
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe:
        return ffmpeg_exe

    # 检查ComfyUI目录中的ffmpeg
    comfyui_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    possible_paths = [
        os.path.join(comfyui_dir, "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.join(comfyui_dir, "ffmpeg.exe"),
        os.path.join(sys.prefix, "Scripts", "ffmpeg.exe"),
        os.path.join(sys.prefix, "bin", "ffmpeg"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return 'ffmpeg'


def check_ffmpeg(bin_path='ffmpeg'):
    """检查FFmpeg是否可用"""
    try:
        # 尝试运行ffmpeg -version
        result = subprocess.run(
            [bin_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ FFmpeg可用")
            print(f"版本: {result.stdout.split('ffmpeg version')[1].split()[0]}")
            return True
        else:
            print("✗ FFmpeg返回错误")
            return False
    except FileNotFoundError:
        print("✗ FFmpeg未找到（不在PATH中）")
        return False
    except Exception as e:
        print(f"✗ 检查FFmpeg时出错: {e}")
        return False


def merge_videos_ffmpeg(video_paths, output_path, method='concat'):
    """
    使用FFmpeg合并视频

    Args:
        ffmpeg_path: 指定ffmpeg路径
        video_paths: 视频文件列表
        output_path: 输出路径
        method: 合并方式
            - 'concat': 直接拼接（需要相同编码）
            - 'reencode': 重新编码合并
    """

    ffmpeg_path = find_ffmpeg()
    print("检查FFmpeg...")
    if not check_ffmpeg(ffmpeg_path):
        raise ModuleNotFoundError("FFmpeg未正确安装或配置")

    if method == 'concat':
        # 方法1：直接拼接（最快，但要求视频规格完全相同）
        concat_file = 'concat_list.txt'

        # 创建拼接列表文件
        with open(concat_file, 'w', encoding='utf-8') as f:
            for video in video_paths:
                f.write(f"file '{os.path.abspath(video)}'\n")

        # 执行FFmpeg命令
        cmd = [
            ffmpeg_path,
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',  # 直接复制，不重新编码
            output_path
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"视频拼接完成: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg执行失败: {e}")
        finally:
            # 清理临时文件
            if os.path.exists(concat_file):
                os.remove(concat_file)

    elif method == 'reencode':
        # 方法2：重新编码合并（兼容性更好）
        filter_complex = ''
        inputs = []

        for i, video in enumerate(video_paths):
            inputs.extend(['-i', video])
            filter_complex += f'[{i}:v:0][{i}:a:0]'

        filter_complex += f'concat=n={len(video_paths)}:v=1:a=1[outv][outa]'

        cmd = [
            ffmpeg_path,
            *inputs,
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            output_path
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"视频合并完成: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg执行失败: {e}")


class SimpleMergeVideosNode(io.ComfyNode):

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="snuabar.video.simple.combine.note",
            display_name="简易视频合并",
            category="SnuabarTools",
            inputs=[
                io.String.Input(
                    id='path',
                    display_name='文件夹',
                ),
                io.Combo.Input(
                    id='input_path_type',
                    display_name='文件夹类型',
                    options=['output', 'custom'],
                    default='output',
                ),
                io.String.Input(
                    id='pattern',
                    display_name='搜索模板',
                    default='*.mp4',
                ),
                io.String.Input(
                    id='file_name',
                    display_name='输出文件名',
                    default='combined.mp4',
                ),
                io.Combo.Input(
                    id='output_path_type',
                    display_name='输出路径类型',
                    options=['same', 'output'],
                    default='same',
                ),
                io.Boolean.Input(
                    id='overwrite',
                    display_name='覆盖已存在',
                    default=False,
                ),
                io.Combo.Input(
                    id='sort_method',
                    display_name='排序方法',
                    options=['none', 'filename', 'creation_time', 'modification_time', 'size', 'duration', 'natural'],
                    default='none',
                ),
                io.Combo.Input(
                    id='sort_order',
                    display_name='排序顺序',
                    options=['ascending', 'descending'],
                    default='ascending',
                ),
                io.Combo.Input(
                    id='merge_method',
                    display_name='合并方法',
                    options=['concat', 'reencode'],
                    default='concat',
                ),
            ],
            outputs=[
                io.String.Output(
                    id='output_file',
                    display_name='输出文件路径'
                )
            ]
        )

    @classmethod
    def execute(cls, path, input_path_type, pattern, file_name, output_path_type, overwrite,
                sort_order, sort_method, merge_method) -> io.NodeOutput:
        # 在ComfyUI节点的代码中添加
        comfy_out_dir = common_fun.get_output_directory()
        if input_path_type.lower() == 'output':
            directory_path = os.path.join(comfy_out_dir, path)
        else:
            directory_path = path
        directory_path = os.path.normpath(os.path.abspath(directory_path))

        # Verify inputs
        if not os.path.exists(directory_path):
            raise ValueError(f"Directory {directory_path} does not exist")

        file_pattern = pattern
        output_filename = file_name
        # Get video files
        video_files = list(Path(directory_path).glob(file_pattern))
        if not video_files:
            raise ValueError(f"No video files matching {file_pattern} found in {directory_path}")

        if sort_method.lower() != 'none':
            video_files = common_fun.VideoFileSorter().sort_videos(video_files, sort_method, sort_order)

        if output_path_type == 'same':
            # Set output path
            output_path = os.path.join(directory_path, output_filename)
        else:
            output_path = os.path.join(comfy_out_dir, output_filename)

        if not os.path.exists(output_path) or overwrite:
            if os.path.exists(output_path):
                os.remove(output_path)
            # 开始合并
            merge_videos_ffmpeg(video_files, output_path, method=merge_method)

        return io.NodeOutput(output_path)

    @classmethod
    def fingerprint_inputs(cls, **kwargs) -> Any:
        return f"{datetime.datetime.now()}"
