"""Thin adapters that execute the pinned UG-Search implementation."""

from __future__ import annotations

import ast
from pathlib import Path
from types import FunctionType

from PIL import Image


FRAMEWORK_ROOT = Path(__file__).resolve().parents[2] / "third_party" / "ug-framework"
QWEN_SOURCE = FRAMEWORK_ROOT / "lmms-eval" / "lmms_eval" / "models" / "qwen2_5_vl.py"
PINNED_COMMIT = "13050ee49865e4330519108f42d1ccfccff1aee1"


def _qwen_class() -> ast.ClassDef:
    tree = ast.parse(QWEN_SOURCE.read_text(encoding="utf-8"), filename=str(QWEN_SOURCE))
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Qwen2_5_VL")


def _method(name: str) -> ast.FunctionDef:
    return next(node for node in _qwen_class().body if isinstance(node, ast.FunctionDef) and node.name == name)


def sliding_windows(image: Image.Image, visual_crop_ratio: float) -> list[tuple[tuple[int, int, int, int], Image.Image]]:
    """Execute the window-position statements from official Qwen2.5-VL UG-Search.

    Loading this AST slice avoids importing lmms-eval's optional dependency graph
    in the CPU harness, while keeping the proposal algorithm owned by the pin.
    """
    branch = next(node for node in ast.walk(_method("generate_until")) if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Attribute) and node.test.attr == "ug_search")
    names = {"width", "height", "box_size", "stride", "x_positions", "y_positions"}
    def belongs(node: ast.stmt) -> bool:
        if isinstance(node, ast.Assign):
            return any(name.id in names for target in node.targets for name in ast.walk(target)
                       if isinstance(name, ast.Name))
        return isinstance(node, ast.If) and any(name.id in {"x_positions", "y_positions"}
                                                for name in ast.walk(node.test) if isinstance(name, ast.Name))
    statements = [node for node in branch.body if belongs(node)]
    namespace = {"original_visual": image, "self": type("Config", (), {"visual_crop_ratio": visual_crop_ratio})()}
    module = ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[]))
    exec(compile(module, str(QWEN_SOURCE), "exec"), namespace)
    size = namespace["box_size"]
    return [((x, y, x + size, y + size), image.crop((x, y, x + size, y + size)).resize(image.size, Image.Resampling.LANCZOS))
            for y in namespace["y_positions"] for x in namespace["x_positions"]]


def entropy_hook(torch: object, functional: object) -> FunctionType:
    """Load UG-Search's exact normalized next-token entropy hook from the pin."""
    module = ast.fix_missing_locations(ast.Module(body=[_method("entropy_hook")], type_ignores=[]))
    namespace: dict[str, object] = {"torch": torch, "F": functional}
    exec(compile(module, str(QWEN_SOURCE), "exec"), namespace)
    return namespace["entropy_hook"]  # type: ignore[return-value]


def assert_pin() -> None:
    if not QWEN_SOURCE.is_file():
        raise RuntimeError("UG framework submodule is missing; run git submodule update --init")
