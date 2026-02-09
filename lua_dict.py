from dataclasses import dataclass
from pathlib import PurePath
from typing import Any

from build_process import Environment, PostProcessCtx

HEADER = '-- GENERATED FILE - DO NOT EDIT'

ENV_TO_IMPORT: dict[Environment, str] = {
    'server': 'game:GetService("ServerScriptService")',
    'client': 'game:GetService("Players").LocalPlayer.PlayerScripts',
    'shared': 'game:GetService("ReplicatedStorage")'
}
ENV_TO_VAR: dict[Environment, str] = {
    'server': 'ServerScriptService',
    'client': 'PlayerScripts',
    'shared': 'ReplicatedStorage'
}


@dataclass
class LuaPath():
    path: PurePath
    relative: bool

    def to_lua(self):
        #convert the path to lua
        #if relative = True, script.Parent.Path.To.Module
        #if relative = False, ReplicatedStorage.Path.To.Module
        return ''


class _LuaDict():
    def __init__(self, ctx: PostProcessCtx, dict: dict[Any, Any]):
        self.ctx = ctx
        self.env_map = {k: v.workdir for k, v in ctx.build_ctxs.items()}

        self.out = self._convert()

    def _convert(self):
        return ''


def convert_dict(ctx: PostProcessCtx, dict: dict[Any, Any]):
    return _LuaDict(ctx, dict).out