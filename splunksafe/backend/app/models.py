from __future__ import annotations
import enum
from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class NodeType(str, enum.Enum):
    FILE = "FILE"
    DIRECTORY = "DIRECTORY"
    MOUNT = "MOUNT"


class FileNode(Base):
    __tablename__ = "file_nodes"
    __table_args__ = (
        UniqueConstraint("full_path", name="uq_file_nodes_full_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_path: Mapped[str] = mapped_column(String(4096), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    type: Mapped[NodeType] = mapped_column(Enum(NodeType), nullable=False)
    size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    permissions: Mapped[str] = mapped_column(String(16), default="rwxr-xr-x", nullable=False)

    parent: Mapped["FileNode | None"] = relationship(
        "FileNode", remote_side="FileNode.id", back_populates="children"
    )
    children: Mapped[list["FileNode"]] = relationship(
        "FileNode",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<FileNode {self.type.value} {self.full_path!r}>"
