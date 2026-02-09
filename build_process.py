from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from annotations import AnnotationRegistry, FileBuildCtx
from parser_schemas import ANNOTATION_PREFIX

type Environment = Literal['server', 'client', 'shared']
FILENAMES = ['*.lua', '*.luau']


@dataclass
class BuildException(Exception):
    message: str
    file: Path
    workdir: Path

    def __post_init__(self):
        super().__init__(self.message)

@dataclass
class ProcessCtx():
    reg: AnnotationRegistry
    workdir: Path

    def error(self, message: str, file: Path):
        raise BuildException(message, file, self.workdir)

type BuildCtxList = dict[Environment, BuildProcessCtx]

@dataclass
class PostProcessCtx(ProcessCtx):
    build_ctxs: BuildCtxList

    def create_file(self, env: Environment, name: str, text: str):
        ctx = self.build_ctxs[env]

        file = ctx.output_root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        
        return file

@dataclass
class BuildProcessCtx(ProcessCtx):
    output_root: Path
    env: Environment

    def process_file(self, file: Path):
        from parser import FileParser

        with file.open('r') as f:
            text = f.read()
            if ANNOTATION_PREFIX in text:
                parser = FileParser(self.reg, file, self)
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
