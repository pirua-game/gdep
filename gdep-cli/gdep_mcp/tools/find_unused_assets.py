"""
gdep-mcp/tools/find_unused_assets.py

High-level tool: 미사용 에셋 감지.
프로젝트에서 다른 에셋에 의해 참조되지 않는 고아 에셋을 탐지한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from gdep.confidence import ConfidenceTier, confidence_footer
from gdep.detector import ProjectKind, detect


def run(project_path: str, scan_dir: str | None = None,
        max_results: int = 50) -> str:
    """
    Find potentially unused assets in the project.

    Scans the project's asset directory and identifies assets that are
    not referenced by any other asset file. Useful for cleaning up
    projects and reducing build size.

    Supports:
    - Unity: Scans .meta GUIDs and cross-references .prefab/.unity/.asset files
    - UE5: Scans .uasset binary references (/Game/... paths)

    Limitations:
    - Assets loaded via code (Resources.Load, soft references) may be falsely
      reported as unused. Check before deleting.
    - Runtime-only references (Addressables, AssetBundles) are partially detected.

    Args:
        project_path: Absolute path to the project Scripts/Source or root directory.
        scan_dir:     Optional. Limit scan to a specific subdirectory.
        max_results:  Maximum results to show (default 50). Pass 0 for unlimited.

    Returns:
        Report of unused assets grouped by type, with file sizes.
    """
    try:
        profile = detect(project_path)

        if profile.kind == ProjectKind.UNITY:
            from gdep.unused_assets import find_unused_unity, format_result
            result = find_unused_unity(project_path, scan_dir)
            output = format_result(result, max_results=max_results if max_results > 0 else 9999)
            tier = ConfidenceTier.MEDIUM
            method = "GUID cross-reference scan"

        elif profile.kind == ProjectKind.UNREAL:
            from gdep.unused_assets import find_unused_ue5, format_result
            result = find_unused_ue5(project_path, scan_dir)
            output = format_result(result, max_results=max_results if max_results > 0 else 9999)
            tier = ConfidenceTier.MEDIUM
            method = "binary asset path cross-reference"

        else:
            return (f"[find_unused_assets] Not supported for {profile.display} projects. "
                    f"Only Unity and UE5 projects are supported.")

        caveat = ("\n\n> ⚠ Assets loaded dynamically via code (Resources.Load, "
                  "soft references, Addressables) may be falsely reported. "
                  "Verify before deleting.")

        return output + caveat + confidence_footer(tier, method)

    except Exception as e:
        return f"[find_unused_assets] Error: {e}"
