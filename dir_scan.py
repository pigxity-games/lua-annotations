from itertools import chain
from pathlib import Path
import re

from annotation_parser import ANNOTATION_PREFIX, Annotation, AnnotationDef, ExtensionContext

FILENAMES = ['*.lua', '*.luau']
ANNOTATION_REGEX = re.compile('^--@.*', re.MULTILINE)

def process_file(file: Path):
    out: list[Annotation] = []
    with file.open('r') as f:
        for line in f.readlines():
            line = line.rstrip()
            if line.startswith(ANNOTATION_PREFIX):
                print(line)
            else:
                continue

    return out

def scan_directory(dir: Path, annotations: list[AnnotationDef]):
    assert dir.is_dir()
    
    matched_files = chain.from_iterable(dir.rglob(pat) for pat in FILENAMES)
    for file in matched_files:
        process_file(file)
                    
                    
def build(workdir: Path):
    ctx = ExtensionContext()

    scan_directory(workdir, ctx.registry)