import tempfile
import unittest
from pathlib import Path

from tools.flutter_cleanup import clean_project, find_flutter_projects, list_subdirs, scan_project


def make_flutter_project(root: Path, name: str, build_bytes: int = 10, with_pods: bool = False) -> Path:
    project = root / name
    project.mkdir(parents=True)
    (project / "pubspec.yaml").write_text("name: " + name)
    build_dir = project / "build"
    build_dir.mkdir()
    (build_dir / "output.bin").write_bytes(b"x" * build_bytes)
    dart_tool = project / ".dart_tool"
    dart_tool.mkdir()
    (dart_tool / "package_config.json").write_text("{}")
    if with_pods:
        pods_dir = project / "ios" / "Pods"
        pods_dir.mkdir(parents=True)
        (pods_dir / "Manifest.lock").write_text("lock")
    return project


class FindFlutterProjectsTests(unittest.TestCase):
    def test_finds_only_dirs_with_pubspec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_flutter_project(root, "app_a")
            make_flutter_project(root, "nested/app_b")
            (root / "not_flutter").mkdir()
            (root / "not_flutter" / "notes.txt").write_text("hi")

            found = find_flutter_projects(root)

            self.assertEqual(
                {p.relative_to(root) for p in found},
                {Path("app_a"), Path("nested/app_b")},
            )


class ListSubdirsTests(unittest.TestCase):
    def test_lists_visible_dirs_sorted_and_skips_hidden_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "zebra").mkdir()
            (root / "Alpha").mkdir()
            (root / ".git").mkdir()
            (root / "notes.txt").write_text("hi")

            result = [p.name for p in list_subdirs(root)]

            self.assertEqual(result, ["Alpha", "zebra"])


class ScanProjectTests(unittest.TestCase):
    def test_reports_only_existing_artifacts_with_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = make_flutter_project(root, "app_a", build_bytes=42, with_pods=True)

            result = scan_project(project)

            relpaths = {a["relpath"] for a in result["artifacts"]}
            self.assertEqual(relpaths, {"build", ".dart_tool", "ios/Pods"})
            self.assertNotIn("ios/Podfile.lock", relpaths)
            build_artifact = next(a for a in result["artifacts"] if a["relpath"] == "build")
            self.assertEqual(build_artifact["size"], 42)
            self.assertEqual(result["total_size"], sum(a["size"] for a in result["artifacts"]))


class CleanProjectTests(unittest.TestCase):
    def test_removes_only_selected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = make_flutter_project(root, "app_a", build_bytes=100, with_pods=True)

            outcome = clean_project(project, ["build", "ios/Pods"])

            self.assertFalse((project / "build").exists())
            self.assertFalse((project / "ios" / "Pods").exists())
            self.assertTrue((project / ".dart_tool").exists())
            self.assertTrue((project / "pubspec.yaml").exists())
            self.assertEqual(set(outcome["removed"]), {"build", "ios/Pods"})
            self.assertGreater(outcome["freed_bytes"], 0)

    def test_ignores_relpaths_that_do_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = make_flutter_project(root, "app_a")

            outcome = clean_project(project, ["ios/Pods", "macos/Podfile.lock"])

            self.assertEqual(outcome["removed"], [])
            self.assertEqual(outcome["freed_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
