from typing import Any

from annotations import ENVIRONMENTS, AnnotationBuildCtx, AnnotationDef, AnnotationRegistry, Extension
from build_process import Environment, PostProcessCtx
from lua_dict import LuaPath, convert_dict
from parser_schemas import LuaModule


class IndexExtension(Extension):
    def __init__(self):
        self.indexes: dict[Environment, Any] = {}
        
        for env in ENVIRONMENTS:
            self.indexes[env] = {}


    def on_post_process(self, ctx: PostProcessCtx):
        for env in ENVIRONMENTS:
            ctx.create_file(env, 'Index.lua', convert_dict(ctx, self.indexes[env]))


    def add_to_index(self, ctx: AnnotationBuildCtx):
        module = ctx.annotation.adornee
        assert isinstance(module, LuaModule)

        self.indexes[ctx.build_ctx.env][module.returned_name] = LuaPath(ctx.parser.file, False)


    def load(self, ctx: AnnotationRegistry):
        ctx.registerAnot(AnnotationDef('indexed', retention='build', on_build=self.add_to_index))
        ctx.registerAnot(AnnotationDef('indexedType', scope='type', retention='build'))