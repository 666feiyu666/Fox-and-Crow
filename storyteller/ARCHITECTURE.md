# Engine architecture

`storyteller/` is an engine with no story of its own. A case in `cases/` supplies
the world; the engine supplies the judgement loop, the state rules, the HTTP
surface, and the page. One process plays one case.

```text
player line (say or do)
    -> POST /api/turn
    -> phase 1: Storyteller rules on the action      (engine skill + case canon)
    -> phase 2: Storyteller narrates the ruling      (engine skill + case canon)
    -> session.py folds the ruling into authoritative state
    -> narration, hints, clock or turn count returned to the page
```

## Two phases, one judgement

- **Ruling** answers one question: given these characters and what this world
  permits, what does this action change? It returns outcome, price in time units,
  meter deltas, new canon facts, a private scene plan, and whether the story ends.
  The player never sees this object.
- **Narration** receives the ruling as final and writes the visible passage from
  it. It may not re-judge, soften a failure, or add consequences the ruling did
  not authorise.

Splitting them keeps judgement auditable: the ruling is structured data the
runtime can validate, while the prose is free.

## Who owns what

| Concern | Owner |
| --- | --- |
| Role, procedure, fairness rules, output contracts | `skills/storyteller/SKILL.md` |
| Canon: cast, places, rules, prohibitions, mechanics | `cases/<case>/world.md` |
| Opening scene, in both languages | `cases/<case>/openings.json` |
| Title, player character, meters, clock, ending floor | `cases/<case>/case.json` |
| What a ruling may do to the session | `backend/session.py` |
| Prompt assembly and the two phase calls | `backend/storyteller.py` |
| Case loading and validation | `backend/case.py` |
| Model transport | `backend/model.py` |
| HTTP surface, sessions, error mapping | `backend/server.py` |
| Playable page, bilingual UI | `web/` |

The skill is not documentation for humans only: it is loaded at startup and sent
with every request, together with the case's `world.md`. Editing either changes
the Storyteller's behaviour without touching Python.

## What the runtime enforces

The Storyteller decides; the runtime refuses what would break the story.

- **Meters.** Every meter named in `case.json` is clamped to its own range and
  only moves by at most 2 per turn. Deltas for meters the case does not declare
  are ignored, not invented.
- **Clock (optional).** When a case declares one, the ruling prices each action in
  units of a day; when the day is spent, the loop either advances (resetting the
  meters the case names) or closes the day. Cases without a clock spend nothing
  and never reset.
- **Facts and time costs.** Both are clamped and deduplicated. An unusable ruling
  is rejected with `502` and the session is left untouched.
- **Ending.** A declared ending is accepted only after the case's `min_turns` and
  any meter thresholds it requires. Earlier claims are recorded as
  `ending_refused` and play continues. This floor stops a single turn from
  skipping the story; it does not replace the Storyteller's judgement.
- **Input.** One line, at most 400 characters, `say` or `do`. One turn in flight
  per session (`409` otherwise), and a failed model call never advances state.

## Current limits

- Sessions live in process memory; a restart clears them.
- Continuity comes from eight recent turns plus established facts, not from a
  full narrative database.
- One process serves one case; a different case means a different deployment.
- Passing tests describe implementation behaviour only. They say nothing about
  narrative quality, Agent capability, author utility, or research validity.
