export type RiskLevel = "SAFE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface RiskReport {
  risk: RiskLevel;
  affectedObjects: number;
  blocked: boolean;
  reason: string | null;
}

export interface CommandResponse {
  stdout: string;
  stderr: string;
  cwd: string;
  exit_code: number;
  risk: RiskReport | null;
}

export interface HistoryEntry {
  id: number;
  command: string;
  cwd: string;
  response: CommandResponse;
}
