from typing_extensions import override

from comfy_api.latest import ComfyExtension, io
from custom_nodes.SnuabarTools.Formatter import StringFormatter


class SnuabarToolsExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            StringFormatter,
        ]


async def comfy_entrypoint() -> SnuabarToolsExtension:  # ComfyUI calls this to load your extension and its nodes.
    return SnuabarToolsExtension()
