import sys
import os

from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

sys.path.append(os.path.dirname(__file__))
from formatter import StringFormatter
from image_auto_select import ImageAutoSelectNote, ImageTempNote
from net_objects import NetParamNote, NetResultNote
from common_nodes import AbsPathNode
from video_tools import SimpleMergeVideosNode
from sd_upscale_assistant import SDUpscaleAssistant
from rife_interpolate import RIFEInterpolateNode
from prompt_save_node import SavePromptNode
from prompt_read_node import ReadPromptNode


class SnuabarToolsExtension(ComfyExtension):
    @override
    async def on_load(self) -> None:
        pass

    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            StringFormatter,
            NetParamNote,
            NetResultNote,
            ImageAutoSelectNote,
            ImageTempNote,
            AbsPathNode,
            SimpleMergeVideosNode,
            SDUpscaleAssistant,
            RIFEInterpolateNode,
            SavePromptNode,
            ReadPromptNode,
        ]


async def comfy_entrypoint() -> SnuabarToolsExtension:  # ComfyUI calls this to load your extension and its nodes.
    return SnuabarToolsExtension()
