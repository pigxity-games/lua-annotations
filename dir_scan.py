from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import default_extension.main as default_extension

from annotations import AnnotationRegistry
from parser_schemas import ANNOTATION_PREFIX, Annotation
from parser import FileParser

type Environment = Literal['server', 'client', 'shared']
FILENAMES = ['*.lua', '*.luau']

def check_relations(list: list[Annotation]):
    for anot in list:
        anot.adef.check_relationships(list)

@dataclass
class BuildProcessCtx():
    reg: AnnotationRegistry
    workdir: Path

    def create_file(self, env: Environment, name: str, text: str):
        pass

    def _process_file(self, file: Path):
        with file.open('r') as f:
            text = f.read()
            if ANNOTATION_PREFIX in text:
                parser = FileParser(self.reg, file.name.split('.')[0])
                parser.parse(text)
                for anot in parser.annotations:
                    print(parser.file_name + ': ' + anot.name)
                    print(anot.args_val)
                    print(anot.kwargs_val)
                return parser

    def scan_directory(self):
        for filename in FILENAMES:
            matched_files = self.workdir.rglob(filename)
            for file in matched_files:
                self._process_file(file)
                        
                    
def build(workdir: Path):
    reg = AnnotationRegistry()
    default_extension.load(reg)

    ctx = BuildProcessCtx(reg, workdir)
    ctx.scan_directory()