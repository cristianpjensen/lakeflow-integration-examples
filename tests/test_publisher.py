import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REAL_GIT = shutil.which("git")


def run_git(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    assert REAL_GIT is not None
    return subprocess.run(
        [REAL_GIT, "-C", str(directory), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def publisher_script() -> str:
    workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text()
    publish_step = workflow.split("      - name: Publish source SHA\n", maxsplit=1)[1]
    return textwrap.dedent(publish_step.split("        run: |\n", maxsplit=1)[1])


class ArtifactPublisherTest(unittest.TestCase):
    def setUp(self) -> None:
        if REAL_GIT is None:
            self.skipTest("git is required")

    def create_repository(self, root: Path) -> tuple[Path, Path, list[str]]:
        origin = root / "origin.git"
        source = root / "source"
        run_git(root, "init", "--bare", "--initial-branch=main", str(origin))
        run_git(root, "init", "--initial-branch=main", str(source))
        run_git(source, "config", "user.name", "Test")
        run_git(source, "config", "user.email", "test@example.com")

        source_shas = []
        for version in range(3):
            (source / "source.txt").write_text(f"version {version}\n")
            run_git(source, "add", "source.txt")
            run_git(source, "commit", "-m", f"Source {version}")
            source_shas.append(run_git(source, "rev-parse", "HEAD").stdout.strip())

        run_git(source, "remote", "add", "origin", str(origin))
        run_git(source, "push", "origin", "main")
        return origin, source, source_shas

    def create_candidate(self, runner_temp: Path, source_sha: str, content: str) -> Path:
        integration_dir = runner_temp / "catalog/integrations-examples" / source_sha / "echo"
        integration_dir.mkdir(parents=True)
        (integration_dir / "integration.py").write_text(content)
        return integration_dir

    def run_publisher(
        self,
        source: Path,
        runner_temp: Path,
        source_sha: str,
        *,
        path: str | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "RUNNER_TEMP": str(runner_temp),
                "SOURCE_SHA": source_sha,
                "PUBLISH_RETRY_MAX_DELAY_SECONDS": "0",
                "PUBLISH_RETRY_TIMEOUT_SECONDS": "30",
            }
        )
        if path is not None:
            environment["PATH"] = path
        return subprocess.run(
            ["bash", "-c", publisher_script()],
            cwd=source,
            env=environment,
            check=check,
            capture_output=True,
            text=True,
        )

    def test_identical_rerun_is_a_noop_and_different_rerun_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            origin, source, source_shas = self.create_repository(root)
            runner_temp = root / "runner"
            integration_dir = self.create_candidate(runner_temp, source_shas[0], "first\n")

            first = self.run_publisher(source, runner_temp, source_shas[0])
            identical = self.run_publisher(source, runner_temp, source_shas[0])
            (integration_dir / "integration.py").write_text("different\n")
            different = self.run_publisher(source, runner_temp, source_shas[0], check=False)

            published = run_git(
                origin,
                "show",
                f"artifacts:integrations-examples/{source_shas[0]}/echo/integration.py",
            ).stdout
            self.assertIn("Artifact commit:", first.stdout)
            self.assertIn("already exist and are identical", identical.stdout)
            self.assertEqual(different.returncode, 1)
            self.assertIn("Refusing to replace immutable artifacts", different.stderr)
            self.assertEqual(published, "first\n")

    def test_non_fast_forward_retry_preserves_both_source_shas(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            origin, source, source_shas = self.create_repository(root)
            first_runner = root / "first-runner"
            self.create_candidate(first_runner, source_shas[0], "first\n")
            self.run_publisher(source, first_runner, source_shas[0])

            publisher = root / "publisher"
            competitor = root / "competitor"
            run_git(root, "clone", str(origin), str(publisher))
            run_git(root, "clone", str(origin), str(competitor))
            runner_temp = root / "racing-runner"
            self.create_candidate(runner_temp, source_shas[1], "second\n")

            wrapper_dir = root / "bin"
            wrapper_dir.mkdir()
            wrapper = wrapper_dir / "git"
            marker = root / "competitor-pushed"
            wrapper.write_text(
                textwrap.dedent(
                    f"""\
                    #!{shutil.which('python3')}
                    import os
                    import pathlib
                    import subprocess
                    import sys

                    real_git = {REAL_GIT!r}
                    marker = pathlib.Path({str(marker)!r})
                    competitor = pathlib.Path({str(competitor)!r})
                    source_sha = {source_shas[2]!r}
                    if len(sys.argv) > 1 and sys.argv[1] == "push" and not marker.exists():
                        marker.write_text("pushed")
                        subprocess.run([real_git, "-C", competitor, "fetch", "origin", "artifacts"], check=True)
                        subprocess.run([real_git, "-C", competitor, "switch", "--force-create", "artifacts", "origin/artifacts"], check=True)
                        destination = competitor / "integrations-examples" / source_sha / "echo"
                        destination.mkdir(parents=True)
                        (destination / "integration.py").write_text("third\\n")
                        subprocess.run([real_git, "-C", competitor, "config", "user.name", "Competitor"], check=True)
                        subprocess.run([real_git, "-C", competitor, "config", "user.email", "competitor@example.com"], check=True)
                        subprocess.run([real_git, "-C", competitor, "add", str(destination)], check=True)
                        subprocess.run([real_git, "-C", competitor, "commit", "-m", "Competing publication"], check=True)
                        subprocess.run([real_git, "-C", competitor, "push", "origin", "HEAD:artifacts"], check=True)
                    os.execv(real_git, [real_git, *sys.argv[1:]])
                    """
                )
            )
            wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)

            result = self.run_publisher(
                publisher,
                runner_temp,
                source_shas[1],
                path=f"{wrapper_dir}:{os.environ['PATH']}",
            )
            published_paths = run_git(origin, "ls-tree", "-r", "--name-only", "artifacts").stdout.splitlines()

            self.assertIn("Artifact commit:", result.stdout)
            for source_sha in source_shas:
                self.assertIn(f"integrations-examples/{source_sha}/echo/integration.py", published_paths)


if __name__ == "__main__":
    unittest.main()
