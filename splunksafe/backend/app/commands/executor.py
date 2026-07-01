from __future__ import annotations
import fnmatch
from sqlalchemy.orm import Session
from app.commands.parser import ParsedCommand, ParseError, parse
from app.commands.risk import RiskAnalyzer
from app.fs.repository import FileRepository, normalize_path
from app.fs.service import FileSystemService, FsError
from app.models import NodeType
from app.schemas import CommandResponse, RiskReport


def _risk_to_schema(risk) -> RiskReport | None:
    if risk is None:
        return None
    return RiskReport(
        risk=risk.level,
        affectedObjects=risk.affected,
        blocked=risk.blocked,
        reason=risk.reason,
    )


class CommandExecutor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FileRepository(db)
        self.svc = FileSystemService(self.repo)
        self.analyzer = RiskAnalyzer(self.repo)

    def run(self, command: str, cwd: str, force: bool) -> CommandResponse:
        try:
            cmd = parse(command)
        except ParseError as exc:
            return CommandResponse(stderr=str(exc), cwd=cwd, exit_code=1)

        risk = self.analyzer.analyze(cmd, cwd, force)
        if risk and risk.blocked:
            self.db.rollback()
            return CommandResponse(
                stderr=f"[BLOCKED] {risk.reason or 'protected path'}",
                cwd=cwd, exit_code=1, risk=_risk_to_schema(risk),
            )

        try:
            result = self._dispatch(cmd, cwd, force)
            self.db.commit()
            result.risk = _risk_to_schema(risk)
            return result
        except FsError as exc:
            self.db.rollback()
            return CommandResponse(stderr=str(exc), cwd=cwd, exit_code=1, risk=_risk_to_schema(risk))
        except Exception as exc:
            self.db.rollback()
            return CommandResponse(stderr=f"internal error: {exc}", cwd=cwd, exit_code=1)

    def _dispatch(self, cmd: ParsedCommand, cwd: str, force: bool) -> CommandResponse:
        handlers = {
            "pwd": self._pwd, "cd": self._cd, "ls": self._ls,
            "mkdir": self._mkdir, "touch": self._touch, "rm": self._rm,
            "cp": self._cp, "mv": self._mv, "find": self._find,
            "tree": self._tree, "du": self._du, "df": self._df,
            "stat": self._stat, "chmod": self._chmod,
            "echo": self._echo, "cat": self._cat, "help": self._help,
        }
        handler = handlers.get(cmd.name)
        if handler is None:
            return CommandResponse(stderr=f"{cmd.name}: command not found", cwd=cwd, exit_code=127)
        return handler(cmd, cwd)

    def _pwd(self, cmd, cwd): return CommandResponse(stdout=cwd, cwd=cwd)

    def _cd(self, cmd, cwd):
        target = normalize_path(cwd, cmd.args[0] if cmd.args else "/")
        node = self.repo.get_by_path(target)
        if node is None:
            return CommandResponse(stderr=f"cd: {cmd.args[0]}: No such file or directory", cwd=cwd, exit_code=1)
        if node.type == NodeType.FILE:
            return CommandResponse(stderr=f"cd: {cmd.args[0]}: Not a directory", cwd=cwd, exit_code=1)
        return CommandResponse(cwd=target)

    def _ls(self, cmd, cwd):
        target = normalize_path(cwd, cmd.args[0]) if cmd.args else cwd
        node = self.repo.get_by_path(target)
        if node is None:
            return CommandResponse(stderr=f"ls: cannot access '{cmd.args[0] if cmd.args else target}': No such file or directory", cwd=cwd, exit_code=1)
        if node.type == NodeType.FILE:
            return CommandResponse(stdout=node.name, cwd=cwd)
        children = self.repo.children(node)
        long = cmd.has("-l")
        if long:
            lines = []
            for c in children:
                t = "d" if c.type != NodeType.FILE else "-"
                sz = self._fmt_size(c.size)
                lines.append(f"{t}{c.permissions}  1 splunk splunk {sz:>8}  {c.name}{'/' if c.type != NodeType.FILE else ''}")
            return CommandResponse(stdout="\n".join(lines), cwd=cwd)
        names = "  ".join(c.name + ("/" if c.type != NodeType.FILE else "") for c in children)
        return CommandResponse(stdout=names, cwd=cwd)

    def _mkdir(self, cmd, cwd):
        parents = cmd.has("-p")
        errors = []
        for arg in cmd.args:
            try:
                self.svc.mkdir(cwd, arg, parents=parents)
            except FsError as e:
                errors.append(f"mkdir: {e}")
        return CommandResponse(stderr="\n".join(errors), cwd=cwd, exit_code=1 if errors else 0)

    def _touch(self, cmd, cwd):
        errors = []
        for arg in cmd.args:
            try:
                self.svc.touch_file(cwd, arg)
            except FsError as e:
                errors.append(f"touch: {e}")
        return CommandResponse(stderr="\n".join(errors), cwd=cwd, exit_code=1 if errors else 0)

    def _rm(self, cmd, cwd):
        recursive = cmd.has("-r", "-R", "--recursive")
        errors = []
        for arg in cmd.args:
            try:
                node = self.svc.require(cwd, arg)
                self.svc.remove(node, recursive)
            except FsError as e:
                errors.append(f"rm: {e}")
        return CommandResponse(stderr="\n".join(errors), cwd=cwd, exit_code=1 if errors else 0)

    def _cp(self, cmd, cwd):
        if len(cmd.args) < 2:
            return CommandResponse(stderr="cp: missing destination file operand", cwd=cwd, exit_code=1)
        recursive = cmd.has("-r", "-R")
        src, dst = cmd.args[0], cmd.args[-1]
        try:
            self.svc.copy(cwd, src, dst, recursive)
        except FsError as e:
            return CommandResponse(stderr=f"cp: {e}", cwd=cwd, exit_code=1)
        return CommandResponse(stdout=f"'{src}' -> '{dst}'", cwd=cwd)

    def _mv(self, cmd, cwd):
        if len(cmd.args) < 2:
            return CommandResponse(stderr="mv: missing destination", cwd=cwd, exit_code=1)
        src, dst = cmd.args[0], cmd.args[-1]
        try:
            self.svc.move(cwd, src, dst)
        except FsError as e:
            return CommandResponse(stderr=f"mv: {e}", cwd=cwd, exit_code=1)
        return CommandResponse(stdout=f"'{src}' -> '{dst}'", cwd=cwd)

    def _find(self, cmd, cwd):
        root_arg = cmd.args[0] if cmd.args else cwd
        root_path = normalize_path(cwd, root_arg)
        root = self.repo.get_by_path(root_path)
        if root is None:
            return CommandResponse(stderr=f"find: '{root_arg}': No such file or directory", cwd=cwd, exit_code=1)
        pattern = cmd.options.get("-name", "*")
        type_filter = cmd.options.get("-type")
        matches = self.repo.find_by_name(root, pattern)
        if type_filter == "f":
            matches = [n for n in matches if n.type == NodeType.FILE]
        elif type_filter == "d":
            matches = [n for n in matches if n.type != NodeType.FILE]
        return CommandResponse(stdout="\n".join(n.full_path for n in matches), cwd=cwd)

    def _tree(self, cmd, cwd):
        root_arg = cmd.args[0] if cmd.args else cwd
        root_path = normalize_path(cwd, root_arg)
        root = self.repo.get_by_path(root_path)
        if root is None:
            return CommandResponse(stderr=f"tree: '{root_arg}': No such file or directory", cwd=cwd, exit_code=1)
        dirs, files = [0], [0]
        def build(node, prefix=""):
            children = self.repo.children(node)
            lines = []
            for i, child in enumerate(children):
                last = i == len(children) - 1
                connector = "└── " if last else "├── "
                extender = "    " if last else "│   "
                suffix = "/" if child.type != NodeType.FILE else ""
                lines.append(prefix + connector + child.name + suffix)
                if child.type != NodeType.FILE:
                    dirs[0] += 1
                    lines.extend(build(child, prefix + extender))
                else:
                    files[0] += 1
            return lines
        lines = [root_path] + build(root)
        lines.append(f"\n{dirs[0]} directories, {files[0]} files")
        return CommandResponse(stdout="\n".join(lines), cwd=cwd)

    def _du(self, cmd, cwd):
        root_arg = cmd.args[0] if cmd.args else cwd
        root_path = normalize_path(cwd, root_arg)
        root = self.repo.get_by_path(root_path)
        if root is None:
            return CommandResponse(stderr=f"du: '{root_arg}': No such file or directory", cwd=cwd, exit_code=1)
        max_depth = int(cmd.options.get("-d", cmd.options.get("--max-depth", "1")))
        lines = []
        def walk(node, depth):
            total = node.size
            for child in self.repo.children(node):
                child_total = walk(child, depth + 1)
                total += child_total
            if depth <= max_depth:
                lines.append(f"{self._fmt_size(total)}\t{node.full_path}")
            return total
        walk(root, 0)
        return CommandResponse(stdout="\n".join(lines), cwd=cwd)

    def _df(self, cmd, cwd):
        out = (
            "Filesystem      1K-blocks      Used Available Use% Mounted on\n"
            "/dev/sdb1       524288000    198312  400000000  40% /opt/splunk/var/lib/splunk"
        )
        return CommandResponse(stdout=out, cwd=cwd)

    def _stat(self, cmd, cwd):
        if not cmd.args:
            return CommandResponse(stderr="stat: missing operand", cwd=cwd, exit_code=1)
        path = normalize_path(cwd, cmd.args[0])
        node = self.repo.get_by_path(path)
        if node is None:
            return CommandResponse(stderr=f"stat: cannot stat '{cmd.args[0]}': No such file or directory", cwd=cwd, exit_code=1)
        t = "d" if node.type != NodeType.FILE else "-"
        out = f"  File: {node.full_path}\n  Size: {node.size}\t Type: {node.type.value}\n  Mode: {t}{node.permissions}\n  Inode: {node.id}"
        return CommandResponse(stdout=out, cwd=cwd)

    def _chmod(self, cmd, cwd):
        if len(cmd.args) < 2:
            return CommandResponse(stderr="chmod: missing operand", cwd=cwd, exit_code=1)
        mode, target = cmd.args[0], cmd.args[1]
        path = normalize_path(cwd, target)
        node = self.repo.get_by_path(path)
        if node is None:
            return CommandResponse(stderr=f"chmod: cannot access '{target}': No such file or directory", cwd=cwd, exit_code=1)
        return CommandResponse(stdout=f"mode of '{path}' changed to {mode}", cwd=cwd)

    def _echo(self, cmd, cwd):
        return CommandResponse(stdout=" ".join(cmd.args), cwd=cwd)

    def _cat(self, cmd, cwd):
        if not cmd.args:
            return CommandResponse(stderr="cat: missing operand", cwd=cwd, exit_code=1)
        path = normalize_path(cwd, cmd.args[0])
        node = self.repo.get_by_path(path)
        if node is None:
            return CommandResponse(stderr=f"cat: {cmd.args[0]}: No such file or directory", cwd=cwd, exit_code=1)
        if node.type != NodeType.FILE:
            return CommandResponse(stderr=f"cat: {cmd.args[0]}: Is a directory", cwd=cwd, exit_code=1)
        return CommandResponse(stdout=f"[binary/config content of {node.name} | {self._fmt_size(node.size)} | {node.permissions}]", cwd=cwd)

    def _help(self, cmd, cwd):
        out = """Available commands:
  ls [-l] [path]          list directory contents
  cd [path]               change directory
  pwd                     print working directory
  mkdir [-p] [path]       create directory
  touch [path]            create empty file
  rm [-r/-rf] [path]      remove file or directory
  cp [-r] [src] [dst]     copy
  mv [src] [dst]          move / rename
  find [root] -name [pat] find files by name
  tree [path]             tree view
  du [-d N] [path]        disk usage
  df [path]               disk free
  stat [path]             file metadata
  chmod [mode] [path]     change permissions
  cat [file]              view file
  echo [text]             print text"""
        return CommandResponse(stdout=out, cwd=cwd)

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size >= 1_048_576:
            return f"{size / 1_048_576:.1f}M"
        if size >= 1024:
            return f"{size // 1024}K"
        return f"{size}B"
