import { useEffect, useRef, useState } from "react";
import { executeCommand } from "../api/client";
import type { HistoryEntry } from "../types";
import { RiskBadge } from "./RiskBadge";

const QUICK_COMMANDS = [
  "ls /opt/splunk",
  "ls -l /opt/splunk/etc",
  "cd /opt/splunk/var/lib/splunk",
  "ls",
  "pwd",
  "tree /opt/splunk/etc",
  "du /opt/splunk",
  "df /opt/splunk",
  "find /opt/splunk -name rawdata",
  "stat /opt/splunk/etc/splunk-launch.conf",
  "mkdir /tmp/newdir",
  "touch /tmp/notes.txt",
  "rm -r /tmp/newdir",
  "chmod 755 /opt/splunk/etc/splunk-launch.conf",
  "rm -rf /opt/splunk",
  "help",
];

let idCounter = 0;

export default function Terminal() {
  const [cwd, setCwd] = useState("/");
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [input, setInput] = useState("");
  const [force, setForce] = useState(false);
  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState(-1);
  const [loading, setLoading] = useState(false);

  const outputRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    outputRef.current?.scrollTo({ top: outputRef.current.scrollHeight });
  }, [entries]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function runCommand(raw: string) {
    const command = raw.trim();
    if (!command) return;

    if (command === "clear") {
      setEntries([]);
      setInput("");
      return;
    }

    setCmdHistory((h) => [command, ...h]);
    setHistIdx(-1);
    setLoading(true);

    try {
      const response = await executeCommand(command, cwd, force);
      setEntries((e) => [
        ...e,
        { id: idCounter++, command, cwd, response },
      ]);
      setCwd(response.cwd);
    } catch (err) {
      setEntries((e) => [
        ...e,
        {
          id: idCounter++,
          command,
          cwd,
          response: {
            stdout: "",
            stderr: `connection error: ${(err as Error).message}`,
            cwd,
            exit_code: 1,
            risk: null,
          },
        },
      ]);
    } finally {
      setLoading(false);
      setInput("");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      runCommand(input);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const next = Math.min(histIdx + 1, cmdHistory.length - 1);
      setHistIdx(next);
      setInput(cmdHistory[next] ?? "");
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = Math.max(histIdx - 1, -1);
      setHistIdx(next);
      setInput(next < 0 ? "" : cmdHistory[next] ?? "");
    }
  }

  return (
    <div className="bg-[#0b0e14] rounded-lg border border-[#2a2f3a] overflow-hidden flex flex-col h-[600px] font-mono">
      <div className="bg-[#13161f] border-b border-[#2a2f3a] flex items-center gap-2 px-3.5 py-2.5">
        <span className="w-3 h-3 rounded-full bg-red-500" />
        <span className="w-3 h-3 rounded-full bg-yellow-500" />
        <span className="w-3 h-3 rounded-full bg-green-500" />
        <span className="text-gray-500 text-xs ml-1.5 font-sans">
          SplunkSafe — virtual Splunk filesystem
        </span>
      </div>

      <div className="bg-[#0f1219] border-b border-[#1e2430] px-3.5 py-1.5 text-xs text-gray-500 flex items-center gap-1.5">
        <span>cwd:</span>
        <span className="text-blue-400">{cwd}</span>
        {loading && <span className="text-gray-600 ml-2 animate-pulse">running…</span>}
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div ref={outputRef} className="flex-1 overflow-y-auto px-3.5 py-2.5 text-[13px] leading-7">
          <div className="text-blue-400">SplunkSafe v1.0 — virtual Splunk filesystem</div>
          <div className="text-blue-400">Seeded: /opt/splunk (windows, linux, netfw indexes)</div>
          <div className="text-gray-300 mb-2">Type 'help' or click a chip. Force checkbox bypasses CRITICAL blocks.</div>

          {entries.map((entry) => (
            <div key={entry.id} className="mb-1">
              <div className="text-emerald-400">
                {entry.cwd}$ {entry.command}
              </div>
              {entry.response.risk && (
                <div className="my-0.5">
                  <RiskBadge risk={entry.response.risk} />
                </div>
              )}
              {entry.response.stdout &&
                entry.response.stdout.split("\n").map((line, i) => (
                  <div key={i} className="text-gray-300 whitespace-pre-wrap break-all">
                    {line}
                  </div>
                ))}
              {entry.response.stderr &&
                entry.response.stderr.split("\n").map((line, i) => (
                  <div key={i} className="text-red-400 whitespace-pre-wrap break-all">
                    {line}
                  </div>
                ))}
            </div>
          ))}
        </div>

        <div className="w-48 bg-[#0c0f17] border-l border-[#1e2430] overflow-y-auto px-2.5 py-2.5 hidden md:block">
          <div className="text-gray-600 text-[10px] uppercase tracking-wide font-sans mb-2">
            quick commands
          </div>
          {QUICK_COMMANDS.map((q) => (
            <div
              key={q}
              onClick={() => {
                setInput(q);
                inputRef.current?.focus();
              }}
              className="text-gray-500 hover:text-blue-300 hover:bg-[#1a1f2e] px-2 py-1 rounded text-[11.5px] cursor-pointer truncate mb-0.5 border border-transparent hover:border-[#2a2f3a]"
              title={q}
            >
              {q}
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-[#1e2430] bg-[#0f1219] flex items-center gap-2 px-3 py-2">
        <span className="text-emerald-400 text-[13px] whitespace-nowrap">
          splunk@safe:~$
        </span>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="type a command..."
          autoComplete="off"
          spellCheck={false}
          className="bg-transparent border-none outline-none text-gray-50 text-[13px] flex-1"
        />
        <div className="flex items-center gap-1">
          <input
            type="checkbox"
            id="force"
            checked={force}
            onChange={(e) => setForce(e.target.checked)}
            className="cursor-pointer accent-emerald-400"
          />
          <label htmlFor="force" className="text-gray-600 text-[11px] cursor-pointer font-sans">
            force
          </label>
        </div>
        <button
          onClick={() => runCommand(input)}
          className="bg-[#0a1f0a] border border-[#1a4a1a] text-emerald-400 px-3.5 py-1 rounded text-xs font-sans hover:bg-[#102810]"
        >
          Run ↵
        </button>
      </div>
    </div>
  );
}
