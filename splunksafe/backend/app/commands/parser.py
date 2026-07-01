from __future__ import annotations
import shlex
from dataclasses import dataclass, field


@dataclass
class ParsedCommand:
    name: str
    args: list[str] = field(default_factory=list)
    flags: set[str] = field(default_factory=set)
    options: dict[str, str] = field(default_factory=dict)
    raw: str = ""

    def has(self, *flags: str) -> bool:
        return any(f in self.flags for f in flags)


class ParseError(Exception):
    pass


VALUE_OPTIONS: dict[str, set[str]] = {
    "find": {"-name", "-type"},
    "du": {"-d", "--max-depth"},
}


def parse(raw: str) -> ParsedCommand:
    raw = raw.strip()
    if not raw:
        raise ParseError("empty command")
    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        raise ParseError(f"parse error: {exc}") from exc

    name, rest = tokens[0], tokens[1:]
    value_opts = VALUE_OPTIONS.get(name, set())
    args: list[str] = []
    flags: set[str] = set()
    options: dict[str, str] = {}
    i = 0

    while i < len(rest):
        tok = rest[i]
        if tok.startswith("-") and len(tok) > 1 and not _looks_like_path(tok):
            if tok in value_opts:
                if i + 1 >= len(rest):
                    raise ParseError(f"option {tok} requires a value")
                options[tok] = rest[i + 1]
                i += 2
                continue
            if tok.startswith("--") and "=" in tok:
                key, val = tok.split("=", 1)
                options[key] = val
                i += 1
                continue
            if tok.startswith("--"):
                flags.add(tok)
                i += 1
                continue
            for ch in tok[1:]:
                flags.add(f"-{ch}")
            i += 1
            continue
        args.append(tok)
        i += 1

    return ParsedCommand(name=name, args=args, flags=flags, options=options, raw=raw)


def _looks_like_path(tok: str) -> bool:
    return tok != "-" and tok[1:2].isdigit() is False and tok.startswith("./")
