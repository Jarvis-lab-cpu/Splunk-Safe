import type { CommandResponse } from "../types";

const BASE_URL = "/api";

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function executeCommand(
  command: string,
  cwd: string,
  force: boolean
): Promise<CommandResponse> {
  return postJSON<CommandResponse>("/execute", { command, cwd, force });
}

export function analyzeCommand(
  command: string,
  cwd: string,
  force: boolean
): Promise<CommandResponse> {
  return postJSON<CommandResponse>("/analyze", { command, cwd, force });
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
