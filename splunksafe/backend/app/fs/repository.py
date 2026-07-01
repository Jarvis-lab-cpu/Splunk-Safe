from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import FileNode, NodeType


def normalize_path(cwd: str, path: str) -> str:
    if path.startswith("/"):
        base_parts: list[str] = []
        raw = path
    else:
        base_parts = [p for p in cwd.split("/") if p]
        raw = path
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if base_parts:
                base_parts.pop()
            continue
        base_parts.append(part)
    return "/" + "/".join(base_parts)


class FileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_path(self, full_path: str) -> FileNode | None:
        stmt = select(FileNode).where(FileNode.full_path == full_path)
        return self.db.scalar(stmt)

    def get_root(self) -> FileNode | None:
        return self.get_by_path("/")

    def children(self, node: FileNode) -> list[FileNode]:
        stmt = (
            select(FileNode)
            .where(FileNode.parent_id == node.id)
            .order_by(FileNode.name)
        )
        return list(self.db.scalars(stmt))

    def descendants(self, node: FileNode) -> list[FileNode]:
        prefix = "/" if node.full_path == "/" else node.full_path + "/"
        stmt = select(FileNode).where(FileNode.full_path.like(prefix + "%"))
        return list(self.db.scalars(stmt))

    def subtree_count(self, node: FileNode) -> int:
        return len(self.descendants(node)) + 1

    def find_by_name(self, root: FileNode, pattern: str) -> list[FileNode]:
        import fnmatch
        candidates = [root, *self.descendants(root)]
        return [n for n in candidates if fnmatch.fnmatch(n.name, pattern)]

    def create(
        self,
        name: str,
        full_path: str,
        parent: FileNode | None,
        node_type: NodeType,
        size: int = 0,
        permissions: str = "rwxr-xr-x",
    ) -> FileNode:
        node = FileNode(
            name=name,
            full_path=full_path,
            parent_id=parent.id if parent else None,
            type=node_type,
            size=size,
            permissions=permissions,
        )
        self.db.add(node)
        self.db.flush()
        return node

    def delete_subtree(self, node: FileNode) -> int:
        victims = self.descendants(node)
        count = len(victims) + 1
        for v in sorted(victims, key=lambda n: n.full_path.count("/"), reverse=True):
            self.db.delete(v)
        self.db.delete(node)
        self.db.flush()
        return count

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
