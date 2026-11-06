import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis_assistant.project_opening import ProjectOpener


class ProjectOpenerTests(unittest.TestCase):
    def test_opens_configured_unreal_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "RunBuildTest.uproject"
            project.write_text("{}", encoding="utf-8")
            _write_config(root, "unreal", "run build", project)

            with patch("jarvis_assistant.project_opening.os.startfile") as startfile:
                result = ProjectOpener(root).open_project("unreal", "run build")

        self.assertEqual(result, "Opening Unreal project Run Build.")
        startfile.assert_called_once_with(str(project))

    def test_opens_configured_roblox_project_with_studio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "devils battlefield file.rbxl"
            project.write_text("place", encoding="utf-8")
            studio = root / "RobloxStudioBeta.exe"
            studio.write_text("exe", encoding="utf-8")
            _write_config(root, "roblox", "devils battlefield", project)

            with patch("jarvis_assistant.project_opening._roblox_studio_executable", return_value=studio), patch(
                "jarvis_assistant.project_opening.subprocess.Popen"
            ) as popen:
                result = ProjectOpener(root).open_project("roblox studio", "battlefield")

        self.assertEqual(result, "Opening Roblox Studio project Devils Battlefield.")
        popen.assert_called_once_with([str(studio), str(project)], shell=False)


def _write_config(root: Path, editor: str, key: str, project: Path) -> None:
    config = root / "config" / "editor_projects.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                editor: {
                    key: {
                        "display_name": key.title(),
                        "path": str(project),
                        "aliases": [key],
                    }
                }
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
