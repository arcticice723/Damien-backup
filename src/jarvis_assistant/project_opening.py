from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


@dataclass(frozen=True)
class EditorProject:
    editor: str
    display_name: str
    path: Path
    aliases: tuple[str, ...] = ()


class ProjectOpener:
    def __init__(self, root: Path, config_path: Path | None = None) -> None:
        self.root = root
        self.config_path = config_path or root / "config" / "editor_projects.json"

    def open_project(self, editor: str, requested_name: str) -> str:
        editor_key = _normalize_editor(editor)
        name = _clean_project_name(requested_name)
        if editor_key not in {"unreal", "roblox"}:
            return "I can open Unreal Engine and Roblox Studio projects right now."
        if not name:
            return f"Which {self._editor_display(editor_key)} project should I open?"
        project = self._resolve_project(editor_key, name)
        if project is None:
            return f"I could not find a {self._editor_display(editor_key)} project named {name}."
        if not project.path.exists():
            return f"I found {project.display_name}, but the project file is missing: {project.path}"
        if editor_key == "roblox":
            return self._open_roblox(project)
        return self._open_unreal(project)

    def _open_unreal(self, project: EditorProject) -> str:
        os.startfile(str(project.path))
        return f"Opening Unreal project {project.display_name}."

    def _open_roblox(self, project: EditorProject) -> str:
        studio = _roblox_studio_executable()
        if studio:
            subprocess.Popen([str(studio), str(project.path)], shell=False)
        else:
            os.startfile(str(project.path))
        return f"Opening Roblox Studio project {project.display_name}."

    def _resolve_project(self, editor: str, requested_name: str) -> EditorProject | None:
        requested = _normalize_project_name(requested_name)
        projects = self._projects(editor)
        if not projects:
            return None
        scored = sorted(
            ((_project_score(requested, project), project) for project in projects),
            key=lambda item: item[0],
            reverse=True,
        )
        return scored[0][1] if scored[0][0] >= 0.72 else None

    def _projects(self, editor: str) -> list[EditorProject]:
        configured = self._configured_projects(editor)
        discovered = self._discover_projects(editor)
        seen = {project.path.resolve() for project in configured if project.path.exists()}
        for project in discovered:
            resolved = project.path.resolve()
            if resolved not in seen:
                configured.append(project)
                seen.add(resolved)
        return configured

    def _configured_projects(self, editor: str) -> list[EditorProject]:
        payload = self._config_payload()
        raw_projects = payload.get(editor, {})
        if not isinstance(raw_projects, dict):
            return []
        projects: list[EditorProject] = []
        for key, value in raw_projects.items():
            if not isinstance(value, dict):
                continue
            path = Path(str(value.get("path", ""))).expanduser()
            aliases = value.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = []
            projects.append(
                EditorProject(
                    editor=editor,
                    display_name=str(value.get("display_name") or key),
                    path=path,
                    aliases=tuple(str(alias) for alias in aliases),
                )
            )
        return projects

    def _discover_projects(self, editor: str) -> list[EditorProject]:
        if editor == "unreal":
            roots = [Path.home() / "Documents" / "Unreal Projects", Path.home() / "Documents"]
            patterns = ("*.uproject",)
        else:
            roots = [Path.home() / "Documents", Path.home() / "Desktop"]
            patterns = ("*.rbxl", "*.rbxlx")
        projects: list[EditorProject] = []
        for root in roots:
            if not root.exists():
                continue
            for pattern in patterns:
                for path in root.rglob(pattern):
                    if _ignored_project_path(path):
                        continue
                    projects.append(
                        EditorProject(
                            editor=editor,
                            display_name=_display_name_from_project(path),
                            path=path,
                        )
                    )
        return projects

    def _config_payload(self) -> dict[str, object]:
        if not self.config_path.exists():
            self._write_default_config()
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {"unreal": {}, "roblox": {}}

    def _write_default_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps({"unreal": {}, "roblox": {}}, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _editor_display(editor: str) -> str:
        return "Unreal Engine" if editor == "unreal" else "Roblox Studio"


def _roblox_studio_executable() -> Path | None:
    versions = Path.home() / "AppData" / "Local" / "Roblox" / "Versions"
    if not versions.exists():
        return None
    candidates = sorted(versions.glob("version-*/RobloxStudioBeta.exe"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _normalize_editor(value: str) -> str:
    normalized = value.casefold()
    if "roblox" in normalized:
        return "roblox"
    if "unreal" in normalized or normalized in {"ue", "ue5"}:
        return "unreal"
    return normalized.strip()


def _clean_project_name(value: str) -> str:
    cleaned = value.strip(" .")
    cleaned = re.sub(r"^(?:project|place|game|called|named|the|my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:project|place|game)$", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" .")


def _normalize_project_name(value: str) -> str:
    cleaned = value.casefold()
    cleaned = re.sub(r"\b(?:project|place|game|file|the|my)\b", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _display_name_from_project(path: Path) -> str:
    name = path.stem
    parent = path.parent.name
    if parent and _normalize_project_name(parent) == _normalize_project_name(name):
        name = parent
    return re.sub(r"\s+", " ", name.replace("_", " ")).strip()


def _ignored_project_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    return bool(parts & {".venv", "site-packages", "__pycache__", "node_modules"})


def _project_score(requested: str, project: EditorProject) -> float:
    names = (project.display_name, project.path.stem, project.path.parent.name, *project.aliases)
    scores = []
    for name in names:
        candidate = _normalize_project_name(name)
        if not candidate:
            continue
        if requested == candidate:
            scores.append(1.0)
            continue
        requested_tokens = set(requested.split())
        candidate_tokens = set(candidate.split())
        overlap = len(requested_tokens & candidate_tokens) / max(len(requested_tokens), 1)
        sequence = SequenceMatcher(None, requested, candidate).ratio()
        if requested_tokens and requested_tokens <= candidate_tokens:
            scores.append(max(sequence, 0.94))
        else:
            scores.append(max(sequence, overlap))
    return max(scores, default=0.0)
