import datetime
import re

from comfy_api.latest import io


class StringFormatter(io.ComfyNode):
    """
    字符串格式化节点

    这个节点允许用户通过指定格式化标记来动态生成字符串。
    支持日期时间格式化以及基本的参数替换功能。

    类方法
    -------------
    define_schema (io.Schema):
        告诉主程序节点的元数据、输入输出参数。
    fingerprint_inputs:
        可选方法，用于控制节点何时重新执行。
    check_lazy_status:
        可选方法，用于控制需要评估的输入名称列表。
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        """
        返回包含节点所有信息的模式定义

        返回值:
            io.Schema: 包含节点ID、显示名称、分类、输入输出参数的模式对象

        输入参数说明:
            - arg1-arg10: 任意类型的可选输入参数
            - string_field: 字符串输入字段，支持多行文本，默认值为"ComfyUI"

        输出参数说明:
            - 返回一个字符串类型的输出
        """
        return io.Schema(
            node_id="SnuabarStringFormatter",
            display_name="StringFormatter",
            category="SnuabarTools",
            inputs=[
                io.AnyType.Input(
                    "arg1",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg2",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg3",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg4",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg5",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg6",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg7",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg8",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg9",
                    optional=True,
                ),
                io.AnyType.Input(
                    "arg10",
                    optional=True,
                ),
                io.String.Input(
                    "string_field",
                    multiline=True,  # 设置为True使字段看起来像ClipTextEncode节点上的字段
                    default="ComfyUI",
                    optional=True,
                    lazy=True,
                ),
            ],
            outputs=[
                io.String.Output(),
            ],
            description="用于格式化字符串的工具节点。",
        )

    @classmethod
    def check_lazy_status(cls,
                          string_field,
                          arg1=None,
                          arg2=None,
                          arg3=None,
                          arg4=None,
                          arg5=None,
                          arg6=None,
                          arg7=None,
                          arg8=None,
                          arg9=None,
                          arg10=None):
        """
        返回需要被评估的输入名称列表

        当存在任何未被评估的延迟输入时，此函数将被调用。
        只要你返回至少一个尚未被评估的字段（且还有更多字段存在），该函数将在请求字段的值可用时再次被调用。

        参数:
            string_field: 字符串字段值
            arg1-arg10: 各个参数的值，已评估的参数会传入，未评估的参数值为None

        返回值:
            list: 需要被评估的输入名称列表
        """
        return ["string_field"]

    @classmethod
    def execute(cls,
                string_field,
                arg1=None,
                arg2=None,
                arg3=None,
                arg4=None,
                arg5=None,
                arg6=None,
                arg7=None,
                arg8=None,
                arg9=None,
                arg10=None) -> io.NodeOutput:
        """
        执行节点逻辑

        节点在输入改变时总是会被重新执行，但此方法可用于强制节点在输入未改变时也重新执行。
        可以让此节点返回数字或字符串，该值将与上次执行时返回的值进行比较，
        如果不同，则节点将被重新执行。

        参数:
            string_field: 字符串字段值
            arg1-arg10: 各个参数的值

        返回值:
            io.NodeOutput: 格式化后的字符串结果
        """
        result = "ComfyUI"
        if string_field:
            # 使用正则表达式查找所有格式化标记
            pattern = r'%([^%:]+):([^%]+)%'
            matches = re.findall(pattern, string_field)
            result = string_field

            # 按照从后往前的顺序替换，避免位置偏移问题
            for match in reversed(matches):
                format_type = match[0]
                format_string = match[1]

                replacement = cls._format_value(format_type, format_string)

                # 替换整个匹配项
                placeholder = f'%{format_type}:{format_string}%'
                result = result.replace(placeholder, replacement)

            if arg1 and "{arg1}" in result:
                result = result.replace("{arg1}", f"{arg1}")
            if arg2 and "{arg2}" in result:
                result = result.replace("{arg2}", f"{arg2}")
            if arg3 and "{arg3}" in result:
                result = result.replace("{arg3}", f"{arg3}")
            if arg4 and "{arg4}" in result:
                result = result.replace("{arg4}", f"{arg4}")
            if arg5 and "{arg5}" in result:
                result = result.replace("{arg5}", f"{arg5}")
            if arg6 and "{arg6}" in result:
                result = result.replace("{arg6}", f"{arg6}")
            if arg7 and "{arg7}" in result:
                result = result.replace("{arg7}", f"{arg7}")
            if arg8 and "{arg8}" in result:
                result = result.replace("{arg8}", f"{arg8}")
            if arg9 and "{arg9}" in result:
                result = result.replace("{arg9}", f"{arg9}")
            if arg10 and "{arg10}" in result:
                result = result.replace("{arg10}", f"{arg10}")

        return io.NodeOutput(result)

    @classmethod
    def _format_value(cls, format_type: str, format_string: str) -> str:
        """
        根据格式类型和格式字符串返回相应的值

        参数:
            format_type: 格式类型，如"date"或"time"
            format_string: 格式字符串，如"yyyy-MM-dd"

        返回值:
            str: 格式化后的字符串
        """
        if format_type == "date":
            return cls._format_datetime(format_string)
        elif format_type == "time":
            return cls._format_time(format_string)
        else:
            # 如果不识别的格式类型，返回原始格式字符串
            return format_string

    @classmethod
    def _format_time(cls, format_string: str) -> str:
        """
        格式化时间

        支持的格式包括：
        - H/h: 小时（1位或2位）
        - m: 分钟（1位或2位）
        - s: 秒（1位或2位）
        - S: 微秒（1-6位）

        参数:
            format_string: 时间格式字符串

        返回值:
            str: 格式化后的时间字符串
        """
        now = datetime.datetime.now()
        result = ""

        # 处理连续的格式字符，如 HHmmss 或 hhmmss
        i = 0
        while i < len(format_string):
            char = format_string[i]

            # 检查是否为连续的相同格式字符
            if char == 'H' or char == 'h':
                # 处理小时格式
                count = 0
                j = i
                while j < len(format_string) and (format_string[j] == 'H' or format_string[j] == 'h'):
                    count += 1
                    j += 1

                if count == 1:
                    result += str(now.hour)
                elif count == 2:
                    result += f"{now.hour:02d}"  # 两位小时
                i = j
                continue
            elif char == 'm':
                # 处理分钟格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 'm':
                    count += 1
                    j += 1

                if count == 1:
                    result += str(now.minute)
                elif count == 2:
                    result += f"{now.minute:02d}"  # 两位分钟
                i = j
                continue
            elif char == 's':
                # 处理秒格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 's':
                    count += 1
                    j += 1

                if count == 1:
                    result += str(now.second)
                elif count == 2:
                    result += f"{now.second:02d}"  # 两位秒
                i = j
                continue
            elif char == 'S':
                # 处理微秒格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 'S':
                    count += 1
                    j += 1

                if count in range(1, 7):
                    ms = now.microsecond // (10 ** (6 - count))
                    result += f"{ms:0{count}d}"
                i = j
                continue
            else:
                # 其他字符直接添加
                result += char
                i += 1

        return result

    @classmethod
    def _format_datetime(cls, format_string: str) -> str:
        """
        格式化日期时间

        支持的格式包括：
        - y: 年份（2位或4位）
        - M: 月份（1位或2位）
        - d: 日期（1位或2位）
        - H/h: 小时（1位或2位）
        - m: 分钟（1位或2位）
        - s: 秒（1位或2位）
        - S: 微秒（1-6位）

        参数:
            format_string: 日期时间格式字符串

        返回值:
            str: 格式化后的日期时间字符串
        """
        now = datetime.datetime.now()
        result = ""

        # 处理连续的格式字符
        i = 0
        while i < len(format_string):
            char = format_string[i]

            # 检查是否为连续的相同格式字符
            if char == 'y':
                # 处理年份格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 'y':
                    count += 1
                    j += 1

                if count == 2:
                    result += str(now.year)[-2:]  # 两位年份
                elif count == 4:
                    result += str(now.year)  # 四位年份
                i = j
                continue
            elif char == 'M':
                # 处理月份格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 'M':
                    count += 1
                    j += 1

                if count == 1:
                    result += str(now.month)
                elif count == 2:
                    result += f"{now.month:02d}"  # 两位月份
                i = j
                continue
            elif char == 'd':
                # 处理日期格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 'd':
                    count += 1
                    j += 1

                if count == 1:
                    result += str(now.day)
                elif count == 2:
                    result += f"{now.day:02d}"  # 两位日期
                i = j
                continue
            elif char == 'H' or char == 'h':
                # 处理小时格式
                count = 0
                j = i
                while j < len(format_string) and (format_string[j] == 'H' or format_string[j] == 'h'):
                    count += 1
                    j += 1

                if count == 1:
                    result += str(now.hour)
                elif count == 2:
                    result += f"{now.hour:02d}"  # 两位小时
                i = j
                continue
            elif char == 'm':
                # 处理分钟格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 'm':
                    count += 1
                    j += 1

                if count == 1:
                    result += str(now.minute)
                elif count == 2:
                    result += f"{now.minute:02d}"  # 两位分钟
                i = j
                continue
            elif char == 's':
                # 处理秒格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 's':
                    count += 1
                    j += 1

                if count == 1:
                    result += str(now.second)
                elif count == 2:
                    result += f"{now.second:02d}"  # 两位秒
                i = j
                continue
            elif char == 'S':
                # 处理微秒格式
                count = 0
                j = i
                while j < len(format_string) and format_string[j] == 'S':
                    count += 1
                    j += 1

                if count in range(1, 7):
                    ms = now.microsecond // (10 ** (6 - count))
                    result += f"{ms:0{count}d}"
                i = j
                continue
            else:
                # 其他字符直接添加
                result += char
                i += 1

        return result

# Set the web directory, any .js file in that directory will be loaded by the frontend as a frontend extension
# WEB_DIRECTORY = "./somejs"
# Add custom API routes, using router
# from aiohttp import web
# from server import PromptServer

# @PromptServer.instance.routes.get("/hello")
# async def get_hello(request):
#     return web.json_response("hello")
