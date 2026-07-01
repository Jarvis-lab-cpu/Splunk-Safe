from __future__ import annotations
from sqlalchemy.orm import Session
from app.fs.repository import FileRepository
from app.models import NodeType


def seed(db: Session) -> None:
    repo = FileRepository(db)
    if repo.get_root() is not None:
        return

    root = repo.create("/", "/", None, NodeType.DIRECTORY)

    etc_top = repo.create("etc", "/etc", root, NodeType.DIRECTORY)
    var_top = repo.create("var", "/var", root, NodeType.DIRECTORY)
    tmp_top = repo.create("tmp", "/tmp", root, NodeType.DIRECTORY)
    repo.create("scratch.txt", "/tmp/scratch.txt", tmp_top, NodeType.FILE, size=512, permissions="rw-r--r--")

    opt = repo.create("opt", "/opt", root, NodeType.DIRECTORY)
    splunk = repo.create("splunk", "/opt/splunk", opt, NodeType.DIRECTORY)
    repo.create("bin", "/opt/splunk/bin", splunk, NodeType.DIRECTORY)

    etc = repo.create("etc", "/opt/splunk/etc", splunk, NodeType.DIRECTORY)
    repo.create("system", "/opt/splunk/etc/system", etc, NodeType.DIRECTORY)
    repo.create("apps", "/opt/splunk/etc/apps", etc, NodeType.DIRECTORY)
    repo.create(
        "splunk-launch.conf", "/opt/splunk/etc/splunk-launch.conf", etc,
        NodeType.FILE, size=2048, permissions="rw-r--r--",
    )
    repo.create(
        "passwd", "/opt/splunk/etc/passwd", etc,
        NodeType.FILE, size=512, permissions="rw-------",
    )

    var = repo.create("var", "/opt/splunk/var", splunk, NodeType.DIRECTORY)
    lib = repo.create("lib", "/opt/splunk/var/lib", var, NodeType.DIRECTORY)
    splunk_mount = repo.create(
        "splunk", "/opt/splunk/var/lib/splunk", lib, NodeType.MOUNT,
    )

    for idx_name in ("windows", "linux", "netfw"):
        idx_path = f"/opt/splunk/var/lib/splunk/{idx_name}"
        idx_node = repo.create(idx_name, idx_path, splunk_mount, NodeType.DIRECTORY)
        for state in ("db", "colddb", "thaweddb"):
            state_path = f"{idx_path}/{state}"
            state_node = repo.create(state, state_path, idx_node, NodeType.DIRECTORY)
            for b in range(15):
                bucket_name = f"db_169{b:02d}_169{b:02d}_{b}"
                bucket_path = f"{state_path}/{bucket_name}"
                bucket_node = repo.create(bucket_name, bucket_path, state_node, NodeType.DIRECTORY)
                repo.create(
                    "rawdata", f"{bucket_path}/rawdata", bucket_node,
                    NodeType.FILE, size=1_048_576, permissions="rw-r--r--",
                )
                repo.create(
                    ".tsidx", f"{bucket_path}/.tsidx", bucket_node,
                    NodeType.FILE, size=262_144, permissions="rw-r--r--",
                )

    repo.commit()
