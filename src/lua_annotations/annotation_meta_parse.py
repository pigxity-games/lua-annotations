
import json
from pathlib import Path
import re
from typing import Any
from lua_annotations.exceptions import BuildError

META_FILE_NAME = 'annotation-meta.json'


def validate_meta_dict(key: Any, value: Any, filename: str, name: str='regex_annotate'):
    if not isinstance(key, str):
        raise BuildError(f'`{name}` key in {filename} must be a string')
    if not isinstance(value, str):
        raise BuildError(f'`{name}["{value}"]` in {filename} must be a string')

def normalize_annotation(annotation: str):
    annotation = annotation.strip()
    if annotation.startswith('--@'):
        return annotation
    if annotation.startswith('@'):
        return f'--{annotation}'
    return f'--@{annotation}'

class AnnotationMeta():
    regex_annotate: dict[re.Pattern[str], str]

    def __init__(self, file: Path):
        # init
        raw = json.loads(file.read_text())
        
        self.regex_annotate = {}

        # regex_annotate
        regex_annotate = raw.get('regex_annotate')
        if not regex_annotate:
            return []
        if not isinstance(regex_annotate, dict):
            raise BuildError(f'`regex_annotate` in {file.as_posix()} must be an object')
        
        for k, v in regex_annotate.items():
            validate_meta_dict(k, v, file.name)
            self.regex_annotate[re.compile(k, re.MULTILINE)] = normalize_annotation(v)

    def process(self, text: str):
        for regex, anot in self.regex_annotate.items():
            text = regex.sub(lambda m: anot + '\n' + m.group(0), text)
        return text