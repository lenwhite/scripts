/**
 * stop-autofmt — pi port of a Claude Code "Stop" hook.
 *
 * Claude Code setup being replicated (from ~/.claude/settings.json):
 *
 *   "hooks": {
 *     "Stop": [{ "hooks": [{ "type": "command", "command":
 *       "jq -r '.transcript_path'
 *          | uv run --script .../claude_code_extract_touched_files.py
 *          | uv run --script .../stop_hook_autofmt.py" }] }]
 *   }
 *
 * The chain does three things when the agent stops:
 *   1. `jq` pulls the transcript path out of the hook's JSON stdin.
 *   2. `extract_touched_files.py` scans the transcript for Write/Edit/`mv`
 *      targets and prints the ones that still exist.
 *   3. `autofmt.py` (the "final script") formats/typechecks/lints those files,
 *      exiting 2 (blocking) with feedback on the first failure.
 *
 * pi port:
 *   - Steps 1+2 are unnecessary — pi hands us tool events directly, so we track
 *     touched files as they happen (write/edit paths + `mv` destinations).
 *   - `agent_settled` is pi's equivalent of Claude Code's `Stop` event: it fires
 *     when pi will not continue on its own.
 *   - We run the SAME vendored `autofmt.py` (the final script), and on a blocking
 *     failure (exit 2) we feed its output back to the model as a follow-up
 *     message — mirroring how Claude Code returns exit-2 stderr to the model.
 *   - Additionally, the FIRST time a run comes back completely clean we hand the
 *     model one extra follow-up: a de-commenting pass. This is unconditional and
 *     fires exactly once per session; no attempt is made to detect whether any
 *     comments were actually added.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";
import type {
  AgentEndEvent,
  ExtensionAPI,
} from "@earendil-works/pi-coding-agent";
import {
  isBashToolResult,
  isEditToolResult,
  isWriteToolResult,
} from "@earendil-works/pi-coding-agent";

// Path to the vendored "final script".
const AUTOFMT_SCRIPT = join(import.meta.dirname, "autofmt.py");

// Blocking exit code used by autofmt.py (see its `sys.exit(2)`).
const BLOCKING_EXIT_CODE = 2;

const STALE_RUNTIME_MARKER = "stale after session replacement or reload";

function isStaleRuntimeError(err: unknown): boolean {
  return err instanceof Error && err.message.includes(STALE_RUNTIME_MARKER);
}

function ifSessionAlive(fn: () => void): void {
  try {
    fn();
  } catch (err) {
    if (!isStaleRuntimeError(err)) throw err;
  }
}

// Safety valve so a check the model cannot satisfy (e.g. a stubborn tsc error)
// does not loop forever, re-triggering the agent on every settle.
const MAX_CONSECUTIVE_BLOCKS = 3;

// One-shot follow-up sent after the first fully-clean run of a session.
const COMMENT_SWEEP_PROMPT = [
  "Auto-format/lint/typecheck passed on the files you just edited.",
  "",
  "One more pass before you stop: remove all comments you added during this",
  "implementation, including docstrings. Comments and docstrings should only be",
  "added when the user specifically asked for them.",
  "",
  "Exception: comments which are outdated should be minimally edited or removed.",
  "",
  "Where needed, change variable names to be more readable and expressive",
  "without comments",
  "",
  "Leave directive/pragma comments (e.g. eslint-disable, ts-expect-error,",
  "type: ignore, noqa) alone.",
  "If you added no comments, just say so and stop.",
].join("\n");

export default function stopAutofmt(pi: ExtensionAPI) {
  // Files touched since the last autofmt run, absolute paths.
  let touched = new Set<string>();
  let running = false;
  let consecutiveBlocks = 0;
  let commentSweepSent = false;
  let userAborted = false;
  let shutdownController = new AbortController();

  const addPath = (cwd: string, p: string | undefined) => {
    if (!p) return;
    touched.add(isAbsolute(p) ? p : resolve(cwd, p));
  };

  const stringField = (
    input: Record<string, unknown>,
    key: string,
  ): string | undefined => {
    const value = input[key];
    return typeof value === "string" ? value : undefined;
  };

  // --- Step 2 replacement: track touched files from tool calls -------------

  pi.on("tool_result", async (event, ctx) => {
    if (event.isError) return; // failed edits/writes did not change disk

    if (isWriteToolResult(event) || isEditToolResult(event)) {
      addPath(ctx.cwd, stringField(event.input, "path"));
      return;
    }

    if (isBashToolResult(event)) {
      const dest = extractMvDestination(
        stringField(event.input, "command") ?? "",
      );
      if (dest) addPath(ctx.cwd, dest);
    }
  });

  pi.on("agent_start", async () => {
    userAborted = false;
  });

  pi.on("agent_end", async (event) => {
    userAborted = endedInUserAbort(event.messages);
  });

  pi.on("session_shutdown", async () => {
    shutdownController.abort();
    shutdownController = new AbortController();
    touched = new Set<string>();
  });

  // --- Step 3: run the final script when the agent stops -------------------

  pi.on("agent_settled", async (_event, ctx) => {
    if (running) return;
    if (userAborted) {
      userAborted = false;
      return;
    }
    if (touched.size === 0) return;

    // Snapshot & reset; only files touched in the next stretch get reformatted.
    const files = [...touched].filter((p) => existsSync(p));
    touched = new Set<string>();
    if (files.length === 0) return;

    const { cwd } = ctx;
    const signal = AbortSignal.any(
      ctx.signal
        ? [ctx.signal, shutdownController.signal]
        : [shutdownController.signal],
    );

    running = true;
    ctx.ui.setStatus("autofmt", "autofmt: running…");
    try {
      const { code, output, aborted } = await runAutofmt(files, cwd, signal);

      ifSessionAlive(() => ctx.ui.setStatus("autofmt", ""));

      if (aborted) {
        for (const file of files) touched.add(file);
        return;
      }

      if (code === 0) {
        consecutiveBlocks = 0;

        // First clean run of the session only: unconditional comment sweep.
        if (!commentSweepSent) {
          commentSweepSent = true;
          ifSessionAlive(() =>
            pi.sendUserMessage(COMMENT_SWEEP_PROMPT, { deliverAs: "followUp" }),
          );
        }
        return;
      }

      if (code === BLOCKING_EXIT_CODE) {
        consecutiveBlocks += 1;

        if (consecutiveBlocks > MAX_CONSECUTIVE_BLOCKS) {
          consecutiveBlocks = 0;
          ifSessionAlive(() =>
            ctx.ui.notify(
              `autofmt still failing after ${MAX_CONSECUTIVE_BLOCKS} attempts; not re-prompting.`,
              "warning",
            ),
          );
          return;
        }

        for (const file of files) touched.add(file);

        // Mirror Claude Code exit-2 behaviour: hand the failure back to the model.
        ifSessionAlive(() =>
          pi.sendUserMessage(
            [
              "Auto-format/lint/typecheck failed on files you just edited.",
              "Fix the problems below, then stop.",
              "",
              output.trim(),
            ].join("\n"),
            { deliverAs: "followUp" },
          ),
        );
        return;
      }

      // Any other non-zero exit: surface it but do not block the model.
      if (output.trim()) {
        ifSessionAlive(() =>
          ctx.ui.notify(
            `autofmt exited ${code}: ${firstLine(output)}`,
            "warning",
          ),
        );
      }
    } catch (err) {
      if (isStaleRuntimeError(err)) return;
      ifSessionAlive(() => {
        ctx.ui.setStatus("autofmt", "");
        ctx.ui.notify(`autofmt error: ${(err as Error).message}`, "error");
      });
    } finally {
      running = false;
    }
  });
}

function endedInUserAbort(messages: AgentEndEvent["messages"]): boolean {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message?.role === "assistant") return message.stopReason === "aborted";
  }
  return false;
}

/** Run the vendored autofmt.py with the touched files, capturing merged output. */
function runAutofmt(
  files: string[],
  cwd: string,
  signal: AbortSignal,
): Promise<{ code: number; output: string; aborted: boolean }> {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn("uv", ["run", "--script", AUTOFMT_SCRIPT, ...files], {
      cwd,
      env: process.env,
    });

    let output = "";
    child.stdout.on("data", (d) => (output += d.toString()));
    child.stderr.on("data", (d) => (output += d.toString()));
    child.on("error", rejectPromise);
    child.on("close", (code, termSignal) =>
      resolvePromise({
        code: code ?? 0,
        output,
        aborted: signal.aborted || termSignal !== null,
      }),
    );

    // Respect Esc / turn cancellation and session teardown.
    if (signal.aborted) {
      child.kill("SIGTERM");
    }
    signal.addEventListener("abort", () => child.kill("SIGTERM"), {
      once: true,
    });
  });
}

/**
 * Best-effort port of extract_mv_destination() from the extract script:
 * only handles the simple `mv <src> <dest>` shape.
 */
function extractMvDestination(command: string): string | null {
  const parts = tokenize(command);
  if (parts.length === 0 || parts[0] !== "mv") return null;
  const args = parts.slice(1).filter((p) => !p.startsWith("-"));
  return args.length === 2 ? (args[1] ?? null) : null;
}

/** Minimal shell tokenizer handling single/double quotes. */
function tokenize(command: string): string[] {
  const tokens: string[] = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(command)) !== null) {
    tokens.push(m[1] ?? m[2] ?? m[3] ?? "");
  }
  return tokens;
}

function firstLine(s: string): string {
  return s.split("\n").find((l) => l.trim()) ?? "";
}
