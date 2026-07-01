from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.commands.executor import CommandExecutor
from app.database import get_db
from app.schemas import CommandRequest, CommandResponse

router = APIRouter(prefix="/api", tags=["splunksafe"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/execute", response_model=CommandResponse)
def execute(req: CommandRequest, db: Session = Depends(get_db)) -> CommandResponse:
    executor = CommandExecutor(db)
    return executor.run(req.command, req.cwd, req.force)


@router.post("/analyze", response_model=CommandResponse)
def analyze(req: CommandRequest, db: Session = Depends(get_db)) -> CommandResponse:
    """Dry-run: returns risk assessment without mutating the filesystem."""
    from app.commands.parser import parse, ParseError
    from app.commands.risk import RiskAnalyzer
    from app.fs.repository import FileRepository
    from app.schemas import RiskReport

    try:
        cmd = parse(req.command)
    except ParseError as exc:
        return CommandResponse(stderr=str(exc), cwd=req.cwd, exit_code=1)

    repo = FileRepository(db)
    analyzer = RiskAnalyzer(repo)
    risk = analyzer.analyze(cmd, req.cwd, req.force)
    risk_report = None
    if risk:
        risk_report = RiskReport(
            risk=risk.level, affectedObjects=risk.affected,
            blocked=risk.blocked, reason=risk.reason,
        )
    return CommandResponse(stdout="dry-run only, no changes applied", cwd=req.cwd, risk=risk_report)
