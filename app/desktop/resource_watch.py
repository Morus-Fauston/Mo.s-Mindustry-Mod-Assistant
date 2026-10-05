"""Bounded on-demand PNG observation; no thread or OS handle survives a session."""
from pathlib import Path
from bisect import bisect_left
from hashlib import sha256
import os

from app.core.project_files import open_project_file


class ResourceWatch:
    MAX_ENTRIES = 10000
    MAX_FILE_BYTES = 16 * 1024 * 1024
    MAX_SCAN_BYTES = 32 * 1024 * 1024
    READ_CHUNK_BYTES = 64 * 1024

    def __init__(self, root: Path):
        self._root = root.resolve()
        self._snapshot: dict = {}
        self._digests: dict[str, bytes] = {}
        self._next_path = ""
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
        # Stat still observes every file. Supported PNGs additionally receive a
        # rotating content check: NTFS can preserve all three stat values during
        # a quick same-size write. Larger unsupported assets remain stat-only.
        digests = {name: digest for name, digest in self._digests.items()
                   if name in snapshot and snapshot[name] == self._snapshot.get(name)}
        names = sorted(name for name, info in snapshot.items()
                       if info[0] <= min(self.MAX_FILE_BYTES, self.MAX_SCAN_BYTES))
        remaining = self.MAX_SCAN_BYTES
        failures = []
        if names:
            start = bisect_left(names, self._next_path) % len(names)
            for offset in range(len(names)):
                index = (start + offset) % len(names)
                name = names[index]
                size = snapshot[name][0]
                self._next_path = name
                if size > remaining:
                    break  # This file starts the next scan, so large files cannot starve.
                # Reserve the entire cost even on failure; all read attempts share
                # one scan budget. A verified handle is closed before moving on.
                remaining -= size
                try:
                    digest = sha256()
                    with open_project_file(self._root, self._root / name) as stream:
                        if os.fstat(stream.fileno()).st_size != size:
                            raise OSError("贴图大小在观察时发生变化")
                        unread = size
                        while unread:
                            chunk = stream.read(min(self.READ_CHUNK_BYTES, unread))
                            if not chunk:
                                raise OSError("贴图在观察时未能完整读取")
                            unread -= len(chunk)
                            digest.update(chunk)
                    digests[name] = digest.digest()
                except (OSError, ValueError) as exc:
                    digests.pop(name, None)
                    failures.append((name, exc))
                self._next_path = names[(index + 1) % len(names)]
        else:
            self._next_path = ""
        changed = snapshot != self._snapshot or digests != self._digests
        self._snapshot = snapshot
        self._digests = digests
        if changed:
            self.revision += 1
        if failures:
            raise OSError(f"贴图内容观察失败：{failures[0][0]}，请刷新后重试") from failures[0][1]
        return changed

    def close(self) -> None:
        self._closed = True
        self._snapshot.clear()
        self._digests.clear()
        self._next_path = ""
