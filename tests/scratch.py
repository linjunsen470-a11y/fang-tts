"""Workspace-local test directories, including on restricted Windows hosts."""
import shutil
import uuid
from pathlib import Path


class ScratchDirectory:
    def __init__(self, prefix="test-"):
        self.base = (Path(__file__).resolve().parents[1] / ".test-tmp").resolve()
        self.base.mkdir(exist_ok=True)
        self.path = self.base / (prefix + uuid.uuid4().hex)
        self.path.mkdir()
        self.name = str(self.path)

    def cleanup(self):
        resolved = self.path.resolve()
        if resolved.parent != self.base or resolved == self.base:
            raise RuntimeError("Test cleanup path is outside the owned scratch directory")
        if resolved.exists():
            shutil.rmtree(resolved)

    def __enter__(self):
        return self.name

    def __exit__(self, *args):
        self.cleanup()
