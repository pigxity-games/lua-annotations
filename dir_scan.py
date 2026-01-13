from itertools import chain
from pathlib import Path
import re

from annotation_parser import Annotation

FILENAMES = ['*.lua', '*.luau']
ANNOTATION_REGEX = re.compile('^--@.*', re.MULTILINE)

def scan_directory(dir: Path):
    assert dir.is_dir()
    out: list[Annotation] = []
    
    matched_files = chain.from_iterable(dir.rglob(pat) for pat in FILENAMES)
    for file in matched_files:
        text = file.read_text()
        for match in ANNOTATION_REGEX.finditer(text):
            print(match.group(0))