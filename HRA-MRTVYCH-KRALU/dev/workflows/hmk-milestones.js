// Workflow script for the Claude Code Workflow tool: builds 1.0 milestones from dev/SPEC-1.0.md.
// Run with args {milestones:[{milestone:'M4', packages:[['M4-A','sonnet'], ...]}], notes:'...'}.
// Preview configs hmk-p1..p5 (ports 8101-8105) and mrtvi-krale (8097) must exist in .claude/launch.json.
export const meta = {
  name: 'hmk-milestones',
  description: 'Hra mrtvých králů 1.0: build milestones in order (parallel work packages per SPEC-1.0, max 5 at once), each followed by its gate; stop on a failed gate',
  phases: [
    { title: 'Build', detail: 'work packages, exclusive file ownership' },
    { title: 'Gate', detail: 'integrate, run milestone acceptance tests, fix' },
  ],
}
const DIR = 'C:\\!Data\\!AI\\!Code\\GitHub\\Games\\HRA-MRTVYCH-KRALU'
const PY = '%LOCALAPPDATA%\\Programs\\Python\\Python314\\python.exe'
const CTX = `
GAME: "Hra mrtvých králů" (1v1 LAN browser game; Python 3.8+ stdlib server + Canvas/HTML client; Czech UI, Czech QWERTZ keyboard → ev.code). Folder: ${DIR}. Python: ${PY} (plain "python" is a Store alias). We are building version 1.0 by the contract ${DIR}\\dev\\SPEC-1.0.md (read §1–5 and §7 fully, then your part of §6; the design docs dev/design-*.md hold details the SPEC cites). Project status: dev/PROGRESS.md. Frozen 0.5 server: dev/tests/golden/server_05.py (never edit).
RULES: edit ONLY the files your package owns (SPEC §6); anything else → put it in 'requests'. Never commit/push/touch git. Never use port 8095 (the user's server). Keep a progress log dev/progress/<your id>.md (update after each step of your work) so an interruption (usage limit) can resume: if it already exists, READ IT FIRST and continue from there instead of starting over (earlier attempts were interrupted). Usage limits are tight: be efficient, test what matters, keep answers short.
`
const REPORT = {
  type: 'object',
  properties: {
    summary: { type: 'string', description: '≤ 150 words' },
    files_changed: { type: 'array', items: { type: 'string' } },
    requests: { type: 'array', items: { type: 'string' }, description: 'changes needed in files you do not own, or decisions for the lead' },
    tests: { type: 'string', description: '≤ 120 words: what ran, results' },
    known_issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary', 'files_changed', 'requests', 'tests', 'known_issues'],
}
const GATE = {
  type: 'object',
  properties: {
    pass: { type: 'boolean' },
    summary: { type: 'string', description: '≤ 200 words' },
    fixed: { type: 'array', items: { type: 'string' } },
    failing: { type: 'array', items: { type: 'string' }, description: 'gate criteria still failing' },
    notes_next: { type: 'string', description: 'what the next milestone must know, ≤ 150 words' },
  },
  required: ['pass', 'summary', 'fixed', 'failing', 'notes_next'],
}

const out = []
let notes = args.notes || ''
for (const ms of args.milestones) {
  const M = ms.milestone
  const pk = []
  for (let w = 0; w < ms.packages.length; w += 5) {
    const wave = ms.packages.slice(w, w + 5)
    const res = await parallel(wave.map(([id, model], i) => () =>
      agent(`${CTX}
YOUR WORK PACKAGE: ${id} of milestone ${M} (SPEC §6). Implement all its deliverables and keep the package rules of §6 (run_fast + golden green, etc.).${notes ? ' Lead notes: ' + notes : ''}
Browser checks (only if your package needs them): use ONLY preview config 'hmk-p${i + 1}' (port ${8101 + i}) via mcp__Claude_Browser__preview_start, your own tabs, then close them and preview_stop. Other packages work in parallel on other files.`,
        { label: `${id}`, phase: 'Build', schema: REPORT, model, effort: model === 'opus' ? 'high' : undefined })
        .then(r => ({ id, ...(r || { summary: 'FAILED/NULL' }) }))))
    pk.push(...res)
  }
  const failedPk = pk.filter(p => p.summary === 'FAILED/NULL').map(p => p.id)
  if (failedPk.length) { log(`${M}: packages failed (${failedPk.join(', ')}), skipping gate`); out.push({ M, failedPk }); break }
  const gate = await agent(`${CTX}
ROLE: MILESTONE ${M} GATE / INTEGRATOR. You may edit any file. The packages just finished: ${JSON.stringify(pk)}
1) Apply the packages' requests that belong to this milestone and resolve cross-package mismatches. 2) Run every ${M} gate criterion from SPEC §6/§7 exactly (headless tests, golden, perf without parallel load, fuzz; browser checks on preview config 'mrtvi-krale' port 8097 — close your tabs and preview_stop afterwards). 3) Fix what fails and re-run. 4) If UI text changed, proofread it (Czech). 5) Update dev/PROGRESS.md (milestone status, done, open issues, how to continue). If dev/progress/${M}-GATE.md exists from an interrupted attempt, read it first and continue. Report pass=true only if every gate criterion passes.`,
    { label: `gate-${M}`, phase: 'Gate', schema: GATE, effort: 'high' })
  out.push({ M, packages: pk.map(p => ({ id: p.id, summary: p.summary })), gate })
  if (!gate || !gate.pass) { log(`${M} gate did not pass, stopping`); break }
  notes = gate.notes_next
  log(`${M} passed`)
}
return out
