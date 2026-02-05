import json
import os

__prompt_json_path = os.path.join(os.path.dirname(__file__), 'workflows')
__upscale_prompt_suffix = '.upscale'


def __get_prompt_file(filename, upscale=False):
    ori_filename = filename
    if upscale:
        filename = filename + __upscale_prompt_suffix
    prompt_path = os.path.join(__prompt_json_path, filename + ".json")
    if os.path.exists(prompt_path):
        return prompt_path
    return __get_prompt_file(ori_filename, False)


def __precheck(workflow_x, class_type, key):
    return ('class_type' in workflow_x and
            class_type in workflow_x['class_type'] and
            'inputs' in workflow_x and
            key in workflow_x['inputs'])


def __get_condition_x(workflow, condition, class_type='Sampler'):
    for x in workflow:
        if __precheck(workflow[x], class_type, condition):
            x0 = workflow[x]['inputs'][condition][0]
            while True:
                if __precheck(workflow[x0], 'TextEncode', 'text'):
                    return x0
                _sub_class_type = workflow[x0]['class_type']
                if __precheck(workflow[x0], _sub_class_type, condition):
                    return workflow[x0]['inputs'][condition][0]
                x0 = workflow[x0]['inputs'][condition][0]
    return None


def __set_prompt_input(workflow, class_type, key, value, x=None):
    if x is not None and x in workflow:
        if __precheck(workflow[x], class_type, key):
            workflow[x]['inputs'][key] = value
        return

    for x in workflow:
        if __precheck(workflow[x], class_type, key):
            workflow[x]['inputs'][key] = value


def __get_prompt_input(workflow, class_type, key, x=None):
    if x is not None and x in workflow:
        if __precheck(workflow[x], class_type, key):
            return workflow[x]['inputs'][key]

    for x in workflow:
        if __precheck(workflow[x], class_type, key):
            return workflow[x]['inputs'][key]

    return None


def __get_upscale_params(width, height, upscale_factor):
    default_mask_blur = 8
    default_tile_padding = 32
    mask_blur = default_mask_blur * upscale_factor
    tile_padding = default_tile_padding * upscale_factor
    tile_width = (width * upscale_factor) // 2
    tile_height = (height * upscale_factor) // 2
    return mask_blur, tile_padding, tile_width, tile_height


def t2i(**kwargs):
    model = kwargs['model'] if 'model' in kwargs else None
    prompt_p = kwargs['prompt_p'] if 'prompt_p' in kwargs else ''
    prompt_n = kwargs['prompt_n'] if 'prompt_n' in kwargs else ''
    width = kwargs['width'] if 'width' in kwargs else 512
    height = kwargs['height'] if 'height' in kwargs else 512
    seed = kwargs['seed'] if 'seed' in kwargs else 0
    step = kwargs['step'] if 'step' in kwargs else 20
    cfg = kwargs['cfg'] if 'cfg' in kwargs else 8.0
    upscale_factor = kwargs['upscale_factor'] if 'upscale_factor' in kwargs else 1.0
    try:
        json_path = __get_prompt_file('t2i', upscale_factor > 1.0)
        with open(json_path, 'r', encoding='utf-8') as f:
            workflow = json.loads(f.read())
        if model is not None and model != "":
            __set_prompt_input(workflow, 'CheckpointLoaderSimple', 'ckpt_name', model)
        if prompt_p is not None and prompt_p != "":
            _x = __get_condition_x(workflow, 'positive')
            __set_prompt_input(workflow, 'CLIPTextEncode', 'text', prompt_p, x=_x)
        if width > 5:
            __set_prompt_input(workflow, 'EmptyLatentImage', 'width', width)
        if height > 5:
            __set_prompt_input(workflow, 'EmptyLatentImage', 'height', height)
        if seed != 0:
            __set_prompt_input(workflow, 'KSampler', 'seed', seed)
            __set_prompt_input(workflow, 'UltimateSDUpscale', 'seed', seed)
        if step != 0:
            __set_prompt_input(workflow, 'KSampler', 'steps', step)
        if cfg != 0.0:
            __set_prompt_input(workflow, 'KSampler', 'cfg', cfg)
            __set_prompt_input(workflow, 'UltimateSDUpscale', 'cfg', cfg)
        if upscale_factor > 1.0:
            __set_prompt_input(workflow, 'UltimateSDUpscale', 'upscale_by', upscale_factor)
            s = __get_prompt_input(workflow, 'KSampler', 'seed')
            __set_prompt_input(workflow, 'UltimateSDUpscale', 'seed', s)
            w = __get_prompt_input(workflow, 'EmptyLatentImage', 'width')
            h = __get_prompt_input(workflow, 'EmptyLatentImage', 'height')
            mask_blur, tile_padding, tile_width, tile_height = __get_upscale_params(w, h, upscale_factor)
            __set_prompt_input(workflow, 'UltimateSDUpscale', 'mask_blur', mask_blur)
            __set_prompt_input(workflow, 'UltimateSDUpscale', 'tile_padding', tile_padding)
            __set_prompt_input(workflow, 'UltimateSDUpscale', 'tile_width', tile_width)
            __set_prompt_input(workflow, 'UltimateSDUpscale', 'tile_height', tile_height)
        return workflow
    except Exception as e:
        print(f"t2i. e: {e}")
        return None


def t2i_wan22(**kwargs):
    prompt_p = kwargs['prompt_p'] if 'prompt_p' in kwargs else ''
    prompt_n = kwargs['prompt_n'] if 'prompt_n' in kwargs else ''
    width = kwargs['width'] if 'width' in kwargs else 512
    height = kwargs['height'] if 'height' in kwargs else 512
    seed = kwargs['seed'] if 'seed' in kwargs else 0
    step = kwargs['step'] if 'step' in kwargs else 10
    cfg = kwargs['cfg'] if 'cfg' in kwargs else 1.0
    upscale_factor = kwargs['upscale_factor'] if 'upscale_factor' in kwargs else 1.0
    try:
        json_path = __get_prompt_file('t2i_wan22', upscale_factor > 1.0)
        with open(json_path, 'r', encoding='utf-8') as f:
            prompt = json.loads(f.read())
        if prompt_p is not None and prompt_p != "":
            _x = __get_condition_x(prompt, 'positive')
            __set_prompt_input(prompt, 'CLIPTextEncode', 'text', prompt_p, x=_x)
        if width > 5:
            __set_prompt_input(prompt, 'WanImageToVideo', 'width', width)
        if height > 5:
            __set_prompt_input(prompt, 'WanImageToVideo', 'height', height)
        if seed != 0:
            __set_prompt_input(prompt, 'KSamplerAdvanced', 'noise_seed', seed)
        if step != 0:
            __set_prompt_input(prompt, 'KSamplerAdvanced', 'steps', step)
        if cfg != 0.0:
            __set_prompt_input(prompt, 'KSamplerAdvanced', 'cfg', cfg)
        if upscale_factor > 1.0:
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'upscale_by', upscale_factor)
            s = __get_prompt_input(prompt, 'KSamplerAdvanced', 'noise_seed')
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'seed', s)
            w = __get_prompt_input(prompt, 'WanImageToVideo', 'width')
            h = __get_prompt_input(prompt, 'WanImageToVideo', 'height')
            mask_blur, tile_padding, tile_width, tile_height = __get_upscale_params(w, h, upscale_factor)
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'mask_blur', mask_blur)
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'tile_padding', tile_padding)
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'tile_width', tile_width)
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'tile_height', tile_height)
        return prompt
    except Exception as e:
        print(f"t2i. e: {e}")
        return None

def t2v_wan22(**kwargs):
    prompt_p = kwargs['prompt_p'] if 'prompt_p' in kwargs else ''
    prompt_n = kwargs['prompt_n'] if 'prompt_n' in kwargs else ''
    width = kwargs['width'] if 'width' in kwargs else 512
    height = kwargs['height'] if 'height' in kwargs else 512
    seed = kwargs['seed'] if 'seed' in kwargs else 0
    step = kwargs['step'] if 'step' in kwargs else 10
    cfg = kwargs['cfg'] if 'cfg' in kwargs else 1.0
    seconds = kwargs['seconds'] if 'seconds' in kwargs else 1
    length = 16 * seconds + 1
    try:
        json_path = __get_prompt_file('t2v_wan22')
        with open(json_path, 'r', encoding='utf-8') as f:
            prompt = json.loads(f.read())
        if prompt_p is not None and prompt_p != "":
            _x = __get_condition_x(prompt, 'positive', "WanImageToVideo")
            __set_prompt_input(prompt, 'CLIPTextEncode', 'text', prompt_p, x=_x)
        if width > 5:
            __set_prompt_input(prompt, 'WanImageToVideo', 'width', width)
        if height > 5:
            __set_prompt_input(prompt, 'WanImageToVideo', 'height', height)
        if length > 1:
            __set_prompt_input(prompt, 'WanImageToVideo', 'length', length)
        if seed != 0:
            __set_prompt_input(prompt, 'WanMoeKSampler', 'seed', seed)
        if step != 0:
            __set_prompt_input(prompt, 'WanMoeKSampler', 'steps', step)
        if cfg != 0.0:
            __set_prompt_input(prompt, 'WanMoeKSampler', 'cfg_high_noise', cfg)
            __set_prompt_input(prompt, 'WanMoeKSampler', 'cfg_low_noise', cfg)
        return prompt
    except Exception as e:
        print(f"t2i. e: {e}")
        return None

def t2v_wan22_lite(**kwargs):
    prompt_p = kwargs['prompt_p'] if 'prompt_p' in kwargs else ''
    prompt_n = kwargs['prompt_n'] if 'prompt_n' in kwargs else ''
    width = kwargs['width'] if 'width' in kwargs else 512
    height = kwargs['height'] if 'height' in kwargs else 512
    seed = kwargs['seed'] if 'seed' in kwargs else 0
    step = kwargs['step'] if 'step' in kwargs else 10
    cfg = kwargs['cfg'] if 'cfg' in kwargs else 1.0
    seconds = kwargs['seconds'] if 'seconds' in kwargs else 1
    length = 16 * seconds + 1
    try:
        json_path = __get_prompt_file('t2v_wan22_lite')
        with open(json_path, 'r', encoding='utf-8') as f:
            prompt = json.loads(f.read())
        if prompt_p is not None and prompt_p != "":
            _x = __get_condition_x(prompt, 'positive', "WanImageToVideo")
            __set_prompt_input(prompt, 'CLIPTextEncode', 'text', prompt_p, x=_x)
        if width > 5:
            __set_prompt_input(prompt, 'WanImageToVideo', 'width', width)
        if height > 5:
            __set_prompt_input(prompt, 'WanImageToVideo', 'height', height)
        if length > 1:
            __set_prompt_input(prompt, 'WanImageToVideo', 'length', length)
        if seed != 0:
            __set_prompt_input(prompt, 'KSampler', 'seed', seed)
        if step != 0:
            __set_prompt_input(prompt, 'KSampler', 'steps', step)
        if cfg != 0.0:
            __set_prompt_input(prompt, 'KSampler', 'cfg', cfg)
        return prompt
    except Exception as e:
        print(f"t2i. e: {e}")
        return None

def t2i_SDXL_turbo(**kwargs):
    prompt_p = kwargs['prompt_p'] if 'prompt_p' in kwargs else ''
    prompt_n = kwargs['prompt_n'] if 'prompt_n' in kwargs else ''
    width = kwargs['width'] if 'width' in kwargs else 512
    height = kwargs['height'] if 'height' in kwargs else 512
    seed = kwargs['seed'] if 'seed' in kwargs else 0
    step = kwargs['step'] if 'step' in kwargs else 4
    cfg = kwargs['cfg'] if 'cfg' in kwargs else 1.0
    upscale_factor = kwargs['upscale_factor'] if 'upscale_factor' in kwargs else 1.0
    try:
        json_path = __get_prompt_file('t2i_SDXL_turbo', upscale_factor > 1.0)
        with open(json_path, 'r', encoding='utf-8') as f:
            prompt = json.loads(f.read())
        if prompt_p is not None and prompt_p != "":
            _x = __get_condition_x(prompt, 'positive')
            __set_prompt_input(prompt, 'CLIPTextEncode', 'text', prompt_p, x=_x)
        if width > 5:
            __set_prompt_input(prompt, 'EmptySD3LatentImage', 'width', width)
        if height > 5:
            __set_prompt_input(prompt, 'EmptySD3LatentImage', 'height', height)
        if seed != 0:
            __set_prompt_input(prompt, 'SamplerCustom', 'noise_seed', seed)
        if step != 0:
            __set_prompt_input(prompt, 'SDTurboScheduler', 'steps', step)
        if cfg != 0.0:
            __set_prompt_input(prompt, 'SamplerCustom', 'cfg', cfg)
        if upscale_factor > 1.0:
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'upscale_by', upscale_factor)
            s = __get_prompt_input(prompt, 'SamplerCustom', 'noise_seed')
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'seed', s)
            w = __get_prompt_input(prompt, 'EmptySD3LatentImage', 'width')
            h = __get_prompt_input(prompt, 'EmptySD3LatentImage', 'height')
            mask_blur, tile_padding, tile_width, tile_height = __get_upscale_params(w, h, upscale_factor)
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'mask_blur', mask_blur)
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'tile_padding', tile_padding)
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'tile_width', tile_width)
            __set_prompt_input(prompt, 'UltimateSDUpscale', 'tile_height', tile_height)
        return prompt
    except Exception as e:
        print(f"t2i. e: {e}")
        return None


workflow_list: dict = {}
workflow_func_map: dict = {}


def load_workflows():
    global workflow_list
    workflow_list.clear()
    with open(__get_prompt_file('model_map'), 'r', encoding='utf-8') as f:
        workflow_list = json.loads(f.read())

    workflow_func_map.clear()
    for key in workflow_list.keys():
        workflow_func_map[key] = globals()[key]
