from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from annotations import AnnotationRegistry, FileBuildCtx
from parser_schemas import ANNOTATION_PREFIX
from parser import FileParser

type Environment = Literal['server', 'client', 'shared']
FILENAMES = ['*.lua', '*.luau']

@dataclass
class BuildException(Exception):
    message: str
    file: Path
    workdir: Path
    env: Environment

    def __post_init__(self):
        super().__init__(self.message)

@dataclass
class BuildProcessCtx():
    reg: AnnotationRegistry
    workdir: Path
    env: Environment

    def create_file(self, env: Environment, name: str, text: str):
        pass

    def error(self, message: str, file: Path):
        raise BuildException(message, file, self.workdir, self.env)

    def process_file(self, file: Path):
        with file.open('r') as f:
            text = f.read()
            if ANNOTATION_PREFIX in text:
                parser = FileParser(self.reg, file.name.split('.')[0])
                parser.parse(text)

                #post-file
                for hook in self.reg.file_build_hooks:
                    hook(FileBuildCtx(self, parser, file))

                return parser

    def process_dir(self):
        for filename in FILENAMES:
            matched_files = self.workdir.rglob(filename)
            for file in matched_files:
                self.process_file(file)