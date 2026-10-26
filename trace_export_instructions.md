# Actual Codex trace export ? pending until this session is finished

The supplied `agent_trace_instructions.md` requires: "Finish the session(s)
you intend to submit, then quit the app or CLI before copying its files."
The current live rollout has therefore not been copied or presented as a final
conversation export. The root `log.txt` is the separate chat_transcript artifact.

After the development work is finished and Codex is closed, open PowerShell in
this repository root and stage the original rollout for this known conversation:

```powershell
$traceRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'sessions' } else { Join-Path $env:USERPROFILE '.codex/sessions' }
$traceFiles = @(Get-ChildItem -LiteralPath $traceRoot -Recurse -File -Filter '*01a16ec5-0280-7651-b7ca-7a2b83d2e0ff*.jsonl')
if ($traceFiles.Count -ne 1) { throw 'Expected one known rollout; inspect the session paths before copying.' }
if (Test-Path -LiteralPath './agent-trace') { throw 'A trace staging directory already exists; preserve and inspect it first.' }
New-Item -ItemType Directory -Path './agent-trace/codex' | Out-Null
Copy-Item -LiteralPath $traceFiles[0].FullName -Destination './agent-trace/codex/'
```

Review the **staged copy** for credentials, secrets, private information and
unrelated material. Redact where necessary without changing the original
rollout. Keep the original JSONL format and original filename. If other actual
sessions/harnesses were used, include only their relevant original traces too;
this known session alone does not prove there were no other sessions.

After that review, create the separately requested archive:

```powershell
if (Test-Path -LiteralPath './agent-trace.zip') { throw 'Trace archive exists; preserve it before creating another.' }
Compress-Archive -Path './agent-trace' -DestinationPath './agent-trace.zip'
```

Inspect the ZIP before uploading. Do not include auth.json, config.toml, settings,
credential stores, the entire .codex directory, unrelated sessions, or nested
archives. Do not put agent-trace.zip inside code.zip. Do not upload anything
without explicit authorization. The portal slot for this additional trace ZIP
has not been independently verified; README separately specifies log.txt for
the chat_transcript slot.
