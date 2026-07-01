from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from app.models import NodeType


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    full_path: str
    parent_id: int | None
    type: NodeType
    size: int
    permissions: str


class CommandRequest(BaseModel):
    command: str
    cwd: str = "/"
    force: bool = False


class RiskReport(BaseModel):
    risk: str
    affectedObjects: int
    blocked: bool
    reason: str | None = None


class CommandResponse(BaseModel):
    stdout: str = ""
    stderr: str = ""
    cwd: str
    exit_code: int = 0
    risk: RiskReport | None = None
