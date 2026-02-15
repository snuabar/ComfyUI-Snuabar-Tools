import datetime
import os

import my_server.ai_image_server as ai_image_server


def get_output_directory():
    try:
        import folder_paths
        return folder_paths.get_output_directory()
    except ImportError:
        return os.getcwd()


def get_today_output_directory():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
    directory = os.path.join(get_output_directory(), timestamp)
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory


def get_before_output_directory(days, make_dirs = True):
    timestamp = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    directory = os.path.join(get_output_directory(), timestamp)
    if not os.path.exists(directory) and make_dirs:
        os.makedirs(directory)
    return directory


ai_image_server.common_functions['get_today_output_directory'] = get_today_output_directory
ai_image_server.common_functions['get_before_output_directory'] = get_before_output_directory


def combine_videos(
        video_files: list[str],
        output_file: str,
        overwrite: bool = False,
        sort_method="creation_time",
        sort_order="ascending"):
    video_files = VideoFileSorter().sort_videos(video_files, sort_method, sort_order)

    if not os.path.exists(output_file) or overwrite:
        if os.path.exists(output_file):
            os.remove(output_file)

    import video_tools
    # 开始合并
    video_tools.merge_videos_ffmpeg(video_files, output_file, method='concat')


ai_image_server.common_functions['combine_videos'] = combine_videos


class VideoFileSorter:
    """视频文件排序，支持多种排序方式"""

    @staticmethod
    def sort_by_filename(video_files, reverse=False):
        """按文件名排序"""
        return sorted(video_files, key=lambda x: os.path.basename(x).lower(), reverse=reverse)

    @staticmethod
    def sort_by_creation_time(video_files, reverse=False):
        """按创建时间排序"""
        return sorted(video_files, key=lambda x: os.path.getctime(x) if os.path.exists(x) else 0, reverse=reverse)

    @staticmethod
    def sort_by_modification_time(video_files, reverse=False):
        """按修改时间排序"""
        return sorted(video_files, key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=reverse)

    @staticmethod
    def sort_by_size(video_files, reverse=False):
        """按文件大小排序"""
        return sorted(video_files, key=lambda x: os.path.getsize(x) if os.path.exists(x) else 0, reverse=reverse)

    @staticmethod
    def sort_by_duration(video_files, reverse=False):
        """按视频时长排序（需要OpenCV）"""
        import cv2

        def get_duration(file_path):
            try:
                cap = cv2.VideoCapture(file_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                cap.release()
                return frame_count / fps if fps > 0 else 0
            except:
                return 0

        return sorted(video_files, key=get_duration, reverse=reverse)

    @staticmethod
    def sort_natural(video_files, reverse=False):
        """自然排序（智能处理数字）"""
        import re

        def natural_key(s):
            return [
                int(text) if text.isdigit() else text.lower()
                for text in re.split(r'(\d+)', os.path.basename(s))
            ]

        return sorted(video_files, key=natural_key, reverse=reverse)

    @classmethod
    def sort_videos(cls, video_files, method='natural', order='ascending'):
        """统一排序接口"""
        if not video_files:
            return []

        reverse = (order.lower() == 'descending')

        sort_methods = {
            'filename': cls.sort_by_filename,
            'creation_time': cls.sort_by_creation_time,
            'modification_time': cls.sort_by_modification_time,
            'size': cls.sort_by_size,
            'duration': cls.sort_by_duration,
            'natural': cls.sort_natural,
        }

        if method in sort_methods:
            return sort_methods[method](video_files, reverse)
        else:
            # 默认使用自然排序
            return cls.sort_natural(video_files, reverse)
