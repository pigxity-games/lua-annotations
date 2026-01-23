from dataclasses import dataclass
from pathlib import Path
import default_extension.main as default_extension

from annotations import ANNOTATION_PREFIX, Annotation, AnnotationRegistry
from lua_parser import parse_block

FILENAMES = ['*.lua', '*.luau']

def check_relations(list: list[Annotation]):
    for anot in list:
        anot.adef.check_relationships(list)

@dataclass
class BuildProcessCtx():
    reg: AnnotationRegistry
    workdir: Path

    def process_file(self, file: Path):
        current_anots: list[Annotation] = []
        
        with file.open('r') as f:
            lines = [l.rstrip() for l in f.readlines()]
            for i, line in enumerate(lines):
                if line.startswith(ANNOTATION_PREFIX):
                    anot = Annotation(self.reg, line)
                    current_anots.append(anot)
                elif line == '' or line.startswith('--'):
                    continue
                else:
                    #if there were annotations in this block of code
                    if len(current_anots) > 0:
                        block = parse_block(lines[i:-1], anot.adef.scope)

                        check_relations(current_anots)
                        current_anots = []

        check_relations(module_anots)

    def scan_directory(self):
        for filename in FILENAMES:
            matched_files = self.workdir.rglob(filename)
            for file in matched_files:
                self.process_file(file)
                        
                    
def build(workdir: Path):
    reg = AnnotationRegistry()
    default_extension.load(reg)

    ctx = BuildProcessCtx(reg, workdir)
    ctx.scan_directory()