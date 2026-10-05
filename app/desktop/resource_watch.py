"""Bounded on-demand PNG observation; no thread or OS handle survives a session."""
from pathlib import Path
import os


class ResourceWatch:
    MAX_ENTRIES = 10000

    def __init__(self, root: Path):
        self._root = root.resolve()
        self._snapshot: dict = {}
        self._closed = False
        self.revision = 0
        self.scan()

    def scan(self) -> bool:
        if self._closed:
            raise ValueError("工程资源观察已关闭")
        directory = self._root / "sprites"
        snapshot = {}
        count = 0
        if directory.is_dir() and directory.resolve().is_relative_to(self._root):
            for base, dirs, files in os.walk(directory, followlinks=False):
                dirs[:] = sorted(name for name in dirs if not (Path(base) / name).is_symlink()
                                 and (Path(base) / name).resolve().is_relative_to(self._root))
                count += len(dirs) + len(files)
                if count > self.MAX_ENTRIES:
                    raise ValueError("贴图目录过大，资源观察已达上限")
                for name in sorted(files):
                    path = Path(base) / name
                    if path.suffix.lower() != ".png" or path.is_symlink():
                        continue
                    try:
                        if not path.resolve().is_relative_to(self._root):
                            continue
                        stat = path.stat()
                        snapshot[path.relative_to(self._root).as_posix()] = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
                    except FileNotFoundError:
                        continue  # A concurrent atomic replacement will be seen next time.
        changed = snapshot != self._snapshot
        self._snapshot = snapshot
        if changed:
            self.revision += 1
        return changed

    def close(self) -> None:
        self._closed = True
        self._snapshot.clear()
