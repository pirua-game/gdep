"""
gdep.unused_assets
Detect unused assets in Unity and UE5 projects.

Builds a set of all referenced asset GUIDs/paths, then scans the project
directory for assets that are not referenced by any other asset.

Works offline — no editor required.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class UnusedAsset:
    """A single unused asset entry."""
    path: str
    name: str
    size_bytes: int = 0
    asset_type: str = ""


@dataclass
class UnusedAssetsResult:
    """Result of unused asset scan."""
    total_assets: int = 0
    unused_count: int = 0
    unused_size_bytes: int = 0
    unused: list[UnusedAsset] = field(default_factory=list)
    engine: str = ""


# ── Unity ─────────────────────────────────────────────────────

# Directories excluded from "unused" detection (they are loaded dynamically)
_UNITY_EXCLUDE_DIRS = {
    "resources", "streamingassets", "plugins", "editor",
    "editor default resources", "gizmos",
}

# File extensions considered as Unity assets
_UNITY_ASSET_EXTS = {
    ".prefab", ".mat", ".asset", ".controller", ".anim",
    ".overridecontroller", ".mask", ".flare", ".renderTexture",
    ".png", ".jpg", ".jpeg", ".tga", ".psd", ".tif", ".tiff",
    ".gif", ".bmp", ".exr", ".hdr",
    ".wav", ".mp3", ".ogg", ".aiff",
    ".fbx", ".obj", ".blend", ".dae",
    ".shader", ".shadergraph", ".shadersubgraph",
    ".ttf", ".otf",
    ".playable", ".signal", ".lighting",
    ".physicmaterial", ".physicsmaterial",
    ".fontsettings", ".guiskin",
    ".mixer",
}


def find_unused_unity(project_path: str,
                      scan_dir: str | None = None) -> UnusedAssetsResult:
    """Find unused assets in a Unity project.

    Algorithm:
    1. Collect all asset GUIDs from .meta files
    2. Scan .prefab/.unity/.asset files to find referenced GUIDs
    3. Add scene GUIDs from EditorBuildSettings (if available)
    4. Report assets whose GUIDs are never referenced
    """
    src = Path(project_path).resolve()

    # Find Assets/ root
    assets_root = None
    for parent in [src] + list(src.parents):
        candidate = parent / "Assets"
        if candidate.is_dir():
            assets_root = candidate
            break
    if not assets_root:
        assets_root = src

    scan_root = Path(scan_dir) if scan_dir else assets_root

    # 1. Collect all asset GUIDs and their paths
    guid_to_path: dict[str, Path] = {}
    for meta_file in assets_root.rglob("*.meta"):
        asset_file = meta_file.with_suffix("")  # Remove .meta
        if not asset_file.exists():
            continue
        if asset_file.is_dir():
            continue
        if asset_file.suffix.lower() not in _UNITY_ASSET_EXTS:
            continue
        # Skip excluded directories
        rel_parts = {p.lower() for p in asset_file.relative_to(assets_root).parts}
        if rel_parts & _UNITY_EXCLUDE_DIRS:
            continue

        try:
            content = meta_file.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                if line.strip().startswith("guid:"):
                    guid = line.split("guid:")[-1].strip()
                    if guid:
                        guid_to_path[guid] = asset_file
                    break
        except Exception:
            continue

    if not guid_to_path:
        return UnusedAssetsResult(engine="Unity")

    # 2. Scan all .prefab, .unity, .asset, .controller files for referenced GUIDs
    referenced_guids: set[str] = set()
    _SCANNABLE = {".prefab", ".unity", ".asset", ".controller",
                  ".anim", ".overridecontroller", ".lighting",
                  ".playable", ".shadergraph"}

    for scannable_file in assets_root.rglob("*"):
        if scannable_file.suffix.lower() not in _SCANNABLE:
            continue
        try:
            content = scannable_file.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r'guid:\s*([0-9a-f]{32})', content):
                referenced_guids.add(match.group(1))
        except Exception:
            continue

    # 3. Build scenes list (always referenced)
    build_settings = assets_root.parent / "ProjectSettings" / "EditorBuildSettings.asset"
    if build_settings.exists():
        try:
            content = build_settings.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r'guid:\s*([0-9a-f]{32})', content):
                referenced_guids.add(match.group(1))
        except Exception:
            pass

    # 4. Find unreferenced assets
    unused: list[UnusedAsset] = []
    total_size = 0

    for guid, asset_path in sorted(guid_to_path.items(), key=lambda x: str(x[1])):
        if guid not in referenced_guids:
            try:
                size = asset_path.stat().st_size
            except Exception:
                size = 0
            total_size += size
            try:
                rel = asset_path.relative_to(assets_root)
            except ValueError:
                rel = asset_path
            unused.append(UnusedAsset(
                path=str(rel),
                name=asset_path.name,
                size_bytes=size,
                asset_type=asset_path.suffix.lstrip('.'),
            ))

    return UnusedAssetsResult(
        total_assets=len(guid_to_path),
        unused_count=len(unused),
        unused_size_bytes=total_size,
        unused=unused,
        engine="Unity",
    )


# ── UE5 ──────────────────────────────────────────────────────

_UE5_ASSET_EXTS = {".uasset", ".umap"}

_UE5_EXCLUDE_DIRS = {
    "__externalactors__", "__externalobjects__",
    "collections", "developers",
}

# Pattern for asset path references in .uasset binaries
_UE5_ASSET_REF_PAT = re.compile(rb'/Game/[\w/]+')


def find_unused_ue5(project_path: str,
                    scan_dir: str | None = None) -> UnusedAssetsResult:
    """Find unused assets in a UE5 project.

    Algorithm:
    1. Collect all .uasset/.umap files under Content/
    2. Scan each file's binary for /Game/... path references
    3. Report assets that are never referenced by any other asset
    """
    from .ue5_blueprint_refs import find_content_root

    content_root = find_content_root(project_path)
    if not content_root:
        return UnusedAssetsResult(engine="UE5")

    scan_root = Path(scan_dir) if scan_dir else content_root

    # 1. Collect all asset files and their /Game/ paths
    asset_files: dict[str, Path] = {}  # game_path → file_path
    for asset_file in content_root.rglob("*"):
        if asset_file.suffix.lower() not in _UE5_ASSET_EXTS:
            continue
        rel_parts = {p.lower() for p in asset_file.relative_to(content_root).parts}
        if rel_parts & _UE5_EXCLUDE_DIRS:
            continue
        try:
            rel = asset_file.relative_to(content_root)
            game_path = "/Game/" + str(rel.with_suffix("")).replace("\\", "/")
            asset_files[game_path] = asset_file
        except ValueError:
            continue

    if not asset_files:
        return UnusedAssetsResult(engine="UE5")

    # 2. Scan each asset for references to other assets
    referenced_paths: set[str] = set()
    for game_path, asset_file in asset_files.items():
        try:
            with open(asset_file, "rb") as f:
                data = f.read()
            for match in _UE5_ASSET_REF_PAT.finditer(data):
                ref_path = match.group(0).decode("utf-8", errors="replace")
                referenced_paths.add(ref_path)
        except Exception:
            continue

    # 3. Add map files referenced in DefaultEngine.ini or DefaultGame.ini
    project_root = content_root.parent
    for ini_name in ("DefaultEngine.ini", "DefaultGame.ini"):
        ini_file = project_root / "Config" / ini_name
        if ini_file.exists():
            try:
                content = ini_file.read_text(encoding="utf-8", errors="replace")
                for match in re.finditer(r'/Game/[\w/]+', content):
                    referenced_paths.add(match.group(0))
            except Exception:
                pass

    # 4. Find unreferenced assets
    unused: list[UnusedAsset] = []
    total_size = 0

    for game_path, asset_file in sorted(asset_files.items()):
        if game_path not in referenced_paths:
            try:
                size = asset_file.stat().st_size
            except Exception:
                size = 0
            total_size += size
            try:
                rel = asset_file.relative_to(content_root)
            except ValueError:
                rel = asset_file
            unused.append(UnusedAsset(
                path=str(rel),
                name=asset_file.name,
                size_bytes=size,
                asset_type=asset_file.suffix.lstrip('.'),
            ))

    return UnusedAssetsResult(
        total_assets=len(asset_files),
        unused_count=len(unused),
        unused_size_bytes=total_size,
        unused=unused,
        engine="UE5",
    )


# ── Formatting ────────────────────────────────────────────────

def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore
    return f"{size_bytes:.1f} TB"


def format_result(result: UnusedAssetsResult, max_results: int = 50) -> str:
    """Format UnusedAssetsResult as console text."""
    lines = [
        f"┌─ Unused Asset Scan ({result.engine}) {'─' * 35}┐",
        f"│ Total assets scanned: {result.total_assets}",
        f"│ Unused assets found:  {result.unused_count}",
        f"│ Wasted space:         {_human_size(result.unused_size_bytes)}",
        f"└{'─' * 60}┘",
        "",
    ]

    if not result.unused:
        lines.append("✓ No unused assets detected.")
        return "\n".join(lines)

    # Group by type
    by_type: dict[str, list[UnusedAsset]] = {}
    for asset in result.unused:
        by_type.setdefault(asset.asset_type, []).append(asset)

    lines.append("── By Type ──")
    for atype, assets in sorted(by_type.items(), key=lambda x: -len(x[1])):
        type_size = sum(a.size_bytes for a in assets)
        lines.append(f"  {atype:<20} {len(assets):>4} files  ({_human_size(type_size)})")

    lines.append("")
    lines.append("── Unused Assets ──")

    shown = result.unused[:max_results]
    for asset in shown:
        size_str = _human_size(asset.size_bytes)
        lines.append(f"  {asset.path:<60} {size_str:>10}")

    if len(result.unused) > max_results:
        lines.append(f"\n... {len(result.unused) - max_results} more assets omitted"
                     f" (use max_results=0 to see all)")

    return "\n".join(lines)
