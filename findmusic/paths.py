"""Choose a writable directory for the Chroma collection."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2


def app_root() -> Path:
    """Project directory when it is writable, otherwise a temp directory.

    Vercel functions can read the deployment and can write only under /tmp.
    """
    override = os.environ.get("FINDMUSIC_ROOT")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path

    root = Path(__file__).resolve().parents[1]
    if _can_write(root / "data"):
        return root

    fallback = Path("/tmp/findmusic")
    fallback.mkdir(parents=True, exist_ok=True)
    _copy_bundled_data(root / "data", fallback / "data")
    os.environ["HOME"] = "/tmp"
    return fallback


def _copy_bundled_data(source: Path, dest: Path) -> None:
    """Copy a read-only deployment collection into writable temporary storage."""
    if not source.is_dir():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        if child.name == "models":
            continue
        target = dest / child.name
        if target.exists():
            continue
        if child.is_dir():
            shutil.copytree(child, target)
        elif child.is_file():
            shutil.copy2(child, target)


def prepare_embedding_cache() -> None:
    """Use a bundled ONNX model when one is present, otherwise a writable cache."""
    bundled = Path(__file__).resolve().parents[1] / "data" / "models" / ONNXMiniLM_L6_V2.MODEL_NAME
    if (bundled / "onnx" / "model.onnx").exists():
        ONNXMiniLM_L6_V2.DOWNLOAD_PATH = bundled
        return
    cache = ONNXMiniLM_L6_V2.DOWNLOAD_PATH
    if (cache / "onnx" / "model.onnx").exists() or _can_write(cache):
        return
    ONNXMiniLM_L6_V2.DOWNLOAD_PATH = Path("/tmp/chroma-onnx") / ONNXMiniLM_L6_V2.MODEL_NAME
    ONNXMiniLM_L6_V2.DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)


def _can_write(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True
