from __future__ import annotations
from dataclasses import dataclass
from app.commands.parser import ParsedCommand
from app.fs.repository import FileRepository, normalize_path
from app.models import NodeType

PROTECTED_PATHS = {
    "/opt",
    "/opt/splunk",
    "/opt/splunk/etc",
    "/opt/splunk/var",
    "/opt/splunk/var/lib",
    "/opt/splunk/var/lib/splunk",
    "/etc",
    "/var",
    "/usr",
    "/bin",
}

DESTRUCTIVE = {"rm", "mv"}


@dataclass
class Risk:
    level: str
    affected: int
    blocked: bool
    reason: str | None = None


class RiskAnalyzer:
    def __init__(self, repo: FileRepository) -> None:
        self.repo = repo

    def analyze(self, cmd: ParsedCommand, cwd: str, force: bool) -> Risk | None:
        if cmd.name not in DESTRUCTIVE:
            return None
        recursive = cmd.has("-r", "-R", "--recursive")
        # NOTE: a command's own "-f"/"--force" flag (e.g. `rm -rf`) must NOT
        # bypass the CRITICAL block on its own — only the explicit `force`
        # parameter (the UI's force checkbox / API's force=true) can.
        # Otherwise `rm -rf /opt/splunk` would silently self-authorize.
        targets = cmd.args[:-1] if cmd.name == "mv" and len(cmd.args) > 1 else cmd.args
        if not targets:
            return None
        worst: Risk | None = None
        for target in targets:
            risk = self._score_target(cmd.name, target, cwd, recursive, force)
            if worst is None or self._rank(risk.level) > self._rank(worst.level):
                worst = risk
        return worst

    def _score_target(self, command: str, target: str, cwd: str, recursive: bool, force_flag: bool) -> Risk:
        abs_path = normalize_path(cwd, target)
        node = self.repo.get_by_path(abs_path)
        if node is None:
            return Risk("LOW", 0, False, f"{target}: no such path")
        affected = self.repo.subtree_count(node)
        is_protected = self._is_protected(abs_path)
        is_dir = node.type in (NodeType.DIRECTORY, NodeType.MOUNT)
        if is_protected and (recursive or not is_dir):
            blocked = not force_flag
            reason = f"{command} targets protected path {abs_path}"
            return Risk("CRITICAL", affected, blocked, reason)
        if is_protected:
            return Risk("HIGH", affected, False, f"{abs_path} is protected but operation is non-recursive")
        if recursive and affected >= 1000:
            return Risk("HIGH", affected, False, f"recursive {command} over {affected} objects")
        if recursive and affected >= 50:
            return Risk("MEDIUM", affected, False, f"recursive {command} over {affected} objects")
        if is_dir and not recursive:
            return Risk("LOW", affected, False, "directory op without -r")
        return Risk("SAFE", affected, False, None)

    @staticmethod
    def _is_protected(path: str) -> bool:
        if path in PROTECTED_PATHS:
            return True
        return path == "/opt/splunk" or path.startswith("/opt/splunk/")

    @staticmethod
    def _rank(level: str) -> int:
        return {"SAFE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}[level]
