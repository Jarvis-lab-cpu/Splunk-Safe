from __future__ import annotations
from app.fs.repository import FileRepository, normalize_path
from app.models import FileNode, NodeType


class FsError(Exception):
    pass


class FileSystemService:
    def __init__(self, repo: FileRepository) -> None:
        self.repo = repo

    def resolve(self, cwd: str, path: str) -> FileNode | None:
        return self.repo.get_by_path(normalize_path(cwd, path))

    def require(self, cwd: str, path: str) -> FileNode:
        node = self.resolve(cwd, path)
        if node is None:
            raise FsError(f"{path}: No such file or directory")
        return node

    def _parent_of(self, full_path: str) -> FileNode:
        parent_path = full_path.rsplit("/", 1)[0] or "/"
        parent = self.repo.get_by_path(parent_path)
        if parent is None:
            raise FsError(f"{parent_path}: No such file or directory")
        if parent.type == NodeType.FILE:
            raise FsError(f"{parent_path}: Not a directory")
        return parent

    def mkdir(self, cwd: str, path: str, parents: bool = False) -> FileNode:
        target_path = normalize_path(cwd, path)
        if self.repo.get_by_path(target_path):
            raise FsError(f"{path}: File exists")
        if parents:
            return self._mkdir_p(target_path)
        parent = self._parent_of(target_path)
        name = target_path.rsplit("/", 1)[1]
        return self.repo.create(
            name=name, full_path=target_path, parent=parent,
            node_type=NodeType.DIRECTORY, permissions="rwxr-xr-x",
        )

    def _mkdir_p(self, target_path: str) -> FileNode:
        parts = [p for p in target_path.split("/") if p]
        node = self.repo.get_root()
        accumulated = ""
        for part in parts:
            accumulated += "/" + part
            existing = self.repo.get_by_path(accumulated)
            if existing:
                if existing.type == NodeType.FILE:
                    raise FsError(f"{accumulated}: Not a directory")
                node = existing
                continue
            node = self.repo.create(
                name=part, full_path=accumulated, parent=node,
                node_type=NodeType.DIRECTORY,
            )
        return node

    def touch_file(self, cwd: str, path: str, size: int = 0) -> FileNode:
        target_path = normalize_path(cwd, path)
        if self.repo.get_by_path(target_path):
            raise FsError(f"{path}: File exists")
        parent = self._parent_of(target_path)
        name = target_path.rsplit("/", 1)[1]
        return self.repo.create(
            name=name, full_path=target_path, parent=parent,
            node_type=NodeType.FILE, size=size, permissions="rw-r--r--",
        )

    def remove(self, node: FileNode, recursive: bool) -> int:
        if node.full_path == "/":
            raise FsError("cannot remove root '/'")
        if node.type != NodeType.FILE and not recursive:
            children = self.repo.children(node)
            if children:
                raise FsError(f"{node.full_path}: Directory not empty")
        return self.repo.delete_subtree(node)

    def _clone_subtree(self, source: FileNode, dest_path: str, dest_parent: FileNode) -> FileNode:
        name = dest_path.rsplit("/", 1)[1]
        new_node = self.repo.create(
            name=name, full_path=dest_path, parent=dest_parent,
            node_type=source.type, size=source.size, permissions=source.permissions,
        )
        for child in self.repo.children(source):
            child_dest = dest_path + "/" + child.name
            self._clone_subtree(child, child_dest, new_node)
        return new_node

    def _resolve_dest(self, source: FileNode, dest: FileNode | None, dest_path: str):
        if dest is not None and dest.type != NodeType.FILE:
            return dest_path.rstrip("/") + "/" + source.name, dest
        parent = self._parent_of(dest_path)
        return dest_path, parent

    def copy(self, cwd: str, src: str, dst: str, recursive: bool) -> FileNode:
        source = self.require(cwd, src)
        if source.type != NodeType.FILE and not recursive:
            raise FsError(f"{src}: -r not specified; omitting directory")
        dest_path_raw = normalize_path(cwd, dst)
        dest_existing = self.repo.get_by_path(dest_path_raw)
        final_path, parent = self._resolve_dest(source, dest_existing, dest_path_raw)
        if self.repo.get_by_path(final_path) and source.type == NodeType.FILE:
            self.repo.delete_subtree(self.repo.get_by_path(final_path))
        return self._clone_subtree(source, final_path, parent)

    def _repath_subtree(self, node: FileNode, new_path: str) -> None:
        node.full_path = new_path
        node.name = new_path.rsplit("/", 1)[1] or "/"
        for child in self.repo.children(node):
            self._repath_subtree(child, new_path.rstrip("/") + "/" + child.name)

    def move(self, cwd: str, src: str, dst: str) -> FileNode:
        source = self.require(cwd, src)
        if source.full_path == "/":
            raise FsError("cannot move root '/'")
        dest_path_raw = normalize_path(cwd, dst)
        if dest_path_raw == source.full_path:
            return source
        if dest_path_raw.startswith(source.full_path + "/"):
            raise FsError("cannot move a directory into itself")
        dest_existing = self.repo.get_by_path(dest_path_raw)
        final_path, parent = self._resolve_dest(source, dest_existing, dest_path_raw)
        clobber = self.repo.get_by_path(final_path)
        if clobber and clobber.id != source.id:
            self.repo.delete_subtree(clobber)
        source.parent_id = parent.id
        self._repath_subtree(source, final_path)
        self.repo.db.flush()
        return source
