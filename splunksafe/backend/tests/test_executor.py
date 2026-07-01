from __future__ import annotations
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.commands.executor import CommandExecutor
from app.database import Base
from app.seed import seed


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed(session)
    yield session
    session.close()


def test_pwd(db):
    res = CommandExecutor(db).run("pwd", "/", False)
    assert res.stdout == "/"


def test_ls_root(db):
    res = CommandExecutor(db).run("ls", "/", False)
    assert "opt" in res.stdout
    assert "etc" in res.stdout


def test_cd_and_pwd(db):
    ex = CommandExecutor(db)
    res = ex.run("cd /opt/splunk/etc", "/", False)
    assert res.cwd == "/opt/splunk/etc"


def test_mkdir_touch_rm(db):
    ex = CommandExecutor(db)
    ex.run("mkdir /tmp/foo", "/", False)
    res = ex.run("ls /tmp", "/", False)
    assert "foo" in res.stdout
    ex.run("touch /tmp/foo/a.txt", "/", False)
    res = ex.run("rm -r /tmp/foo", "/", False)
    assert res.exit_code == 0
    res = ex.run("ls /tmp", "/", False)
    assert "foo" not in res.stdout


def test_critical_path_blocked_without_force(db):
    res = CommandExecutor(db).run("rm -rf /opt/splunk", "/", False)
    assert res.exit_code == 1
    assert res.risk is not None
    assert res.risk.risk == "CRITICAL"
    assert res.risk.blocked is True
    assert "[BLOCKED]" in res.stderr


def test_critical_path_allowed_with_force(db):
    res = CommandExecutor(db).run("rm -rf /opt/splunk", "/", True)
    assert res.risk.blocked is False
    check = CommandExecutor(db).run("ls /opt", "/", False)
    assert "splunk" not in check.stdout


def test_cp_and_mv(db):
    ex = CommandExecutor(db)
    ex.run("touch /tmp/a.txt", "/", False)
    ex.run("cp /tmp/a.txt /tmp/b.txt", "/", False)
    res = ex.run("ls /tmp", "/", False)
    assert "a.txt" in res.stdout and "b.txt" in res.stdout
    ex.run("mv /tmp/b.txt /tmp/c.txt", "/", False)
    res = ex.run("ls /tmp", "/", False)
    assert "c.txt" in res.stdout and "b.txt" not in res.stdout


def test_find_rawdata(db):
    res = CommandExecutor(db).run("find /opt/splunk -name rawdata", "/", False)
    assert "rawdata" in res.stdout
    assert res.stdout.count("rawdata") > 1


def test_unknown_command(db):
    res = CommandExecutor(db).run("frobnicate", "/", False)
    assert res.exit_code == 127
    assert "command not found" in res.stderr
