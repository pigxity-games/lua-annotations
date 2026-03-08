import json
from pathlib import Path

from lua_annotations.api.annotations import AnnotationDef, FileBuildCtx, SortedRegistry
from lua_annotations.build_process import BuildProcessCtx, Workspace
from lua_annotations.parser import FileParser


def make_workspace(root: Path) -> Workspace:
    return {
        "server": {root: ":"},
        "client": {},
        "shared": {},
    }


def test_annotation_meta_regex_annotates_direct_children_only(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    nested = src / "nested"
    nested.mkdir()

    (src / "annotation-meta.json").write_text(
        json.dumps(
            {
                "regex_annotate": {
                    r"^local \w+ = [\w{}]+": "@moduleAnn"
                }
            }
        )
    )

    (src / "Top.lua").write_text(
        """local Top = {}

return {
    Top = Top
}
"""
    )
    (nested / "Nested.lua").write_text(
        """local Nested = {}

return {
    Nested = Nested
}
"""
    )

    parsed: dict[str, FileParser] = {}

    def capture(ctx: FileBuildCtx):
        parsed[ctx.filepath.name] = ctx.parser

    reg = SortedRegistry(
        file_build_hooks=[capture],
        post_build_hooks=[],
        anot_registry={"moduleAnn": AnnotationDef("moduleAnn", scope="module")},
    )

    build_ctx = BuildProcessCtx(
        reg=reg,
        root_dir=tmp_path,
        workspace=make_workspace(src),
        workdirs={src: ":"},
        output_root=tmp_path / "Generated",
        env="server",
    )
    build_ctx.process_dir(src)

    assert "Top.lua" in parsed
    assert "Nested.lua" not in parsed
    assert parsed["Top.lua"].annotations[0].name == "moduleAnn"


def test_annotation_meta_accepts_annotation_without_prefix(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()

    (src / "annotation-meta.json").write_text(
        json.dumps(
            {
                "regex_annotate": {
                    r"^local \w+ = [\w{}]+": "moduleAnn"
                }
            }
        )
    )

    (src / "Top.lua").write_text(
        """local Top = {}

return {
    Top = Top
}
"""
    )

    parsed: dict[str, FileParser] = {}

    def capture(ctx: FileBuildCtx):
        parsed[ctx.filepath.name] = ctx.parser

    reg = SortedRegistry(
        file_build_hooks=[capture],
        post_build_hooks=[],
        anot_registry={"moduleAnn": AnnotationDef("moduleAnn", scope="module")},
    )

    build_ctx = BuildProcessCtx(
        reg=reg,
        root_dir=tmp_path,
        workspace=make_workspace(src),
        workdirs={src: ":"},
        output_root=tmp_path / "Generated",
        env="server",
    )
    build_ctx.process_dir(src)

    assert "Top.lua" in parsed
    assert parsed["Top.lua"].annotations[0].name == "moduleAnn"
