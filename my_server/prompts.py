import json
import os

__prompt_json_path = os.path.join(os.path.dirname(__file__), 'prompts')


def __get_prompt_file(filename):
    return os.path.join(__prompt_json_path, filename)


def t2i(positive_prompt='', seed=0, width=0, height=0):
    try:
        json_path = __get_prompt_file('t2i.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            prompt = json.loads(f.read())
        if positive_prompt is not None and positive_prompt != "":
            prompt['1']['inputs']['text'] = positive_prompt
        if width > 5:
            prompt['2']['inputs']['width'] = width
        if height > 5:
            prompt['2']['inputs']['height'] = height
        if seed != 0:
            prompt['5']['inputs']['seed'] = seed

        return prompt
    except Exception as e:
        print(f"t2i. e: {e}")
        return None



def t2i_wan22(positive_prompt='', seed=0, width=0, height=0):
    try:
        json_path = __get_prompt_file('t2i_wan2.2.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            prompt = json.loads(f.read())
        if positive_prompt is not None and positive_prompt != "":
            prompt['91']['inputs']['text'] = positive_prompt
        if width > 5:
            prompt['28']['inputs']['width'] = width
        if height > 5:
            prompt['28']['inputs']['height'] = height
        if seed != 0:
            prompt['22']['inputs']['noise_seed'] = seed
            prompt['23']['inputs']['noise_seed'] = seed

        return prompt
    except Exception as e:
        print(f"t2i. e: {e}")
        return None

