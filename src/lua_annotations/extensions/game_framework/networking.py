from typing import Any

from api.annotations import AnnotationBuildCtx, AnnotationDef, ExtensionRegistry, Extension
from build_process import PostProcessCtx
from parser_schemas import Annotation, LuaMethod

REMOTE_INSTANCE_MAP = {
    'function': 'RemoteFunction',
    'event': 'RemoteEvent',
    'unreliable': 'UnreliableRemoteEvent',
}


class NetworkingExtension(Extension):
    def __init__(self):
        self.remotes: dict[Any, Any] = {}
        
    
    def remote_on_build(self, ctx: AnnotationBuildCtx):
        anot: Annotation = ctx.annotation
        adornee = anot.adornee
        assert isinstance(adornee, LuaMethod)

        class_name = REMOTE_INSTANCE_MAP[ctx.annotation.args_val[0]]
        module_name = adornee.module.returned_name

        anot.export_data["remote_name"] = adornee.name
        anot.export_data["remote_parent"] = module_name

        self.remotes.setdefault(module_name, {"ClassName": "Folder", "Children": {}})
        self.remotes[module_name]["Children"][adornee.name] = {"ClassName": class_name}


    def on_post_process(self, ctx: PostProcessCtx):
        #Convert dict to valid .model.json format
        root_children = []

        for module_name, module_data in self.remotes.items():
            module_children_map = module_data.get("Children", {})
            module_children = []

            for remote_name, remote_data in module_children_map.items():
                module_children.append({
                    "Name": remote_name,
                    "ClassName": remote_data["ClassName"],
                })

            root_children.append({
                "Name": module_name,
                "ClassName": "Folder",
                "Children": module_children,
            })

        model = {
            "ClassName": "Folder",
            "Children": root_children,
        }

        ctx.dump_json("shared", "Remotes.model.json", model)


    def load(self, ctx: ExtensionRegistry):
        ctx.register_anot(
            AnnotationDef('remote', scope='method', retention='init', args=[str], on_build=self.remote_on_build)
        )
