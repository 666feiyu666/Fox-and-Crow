# Storyteller runtime architecture

The Fox and the Crow is now a playable story with an omniscient Storyteller. The
Storyteller is the agent: it holds the whole world, judges what each line of the
player changes, and narrates the consequence. There is no branching script and no
Twine build.

```text
player line (say or do)
    -> POST /api/turn
    -> phase 1: Storyteller rules on the action      (skill + world canon)
    -> phase 2: Storyteller narrates the ruling      (skill + world canon)
    -> session.py folds the ruling into authoritative state
    -> narration, hints, day and loop returned to the page
```

## Two phases, one judgement

- **Ruling** answers a single question: given these characters and this world,
  what does this action change? It returns outcome, price in time units,
  relationship and insight deltas, new canon facts, a private scene plan, and
  whether the loop ends. The player never sees this object.
- **Narration** receives the ruling as final and writes the visible passage from
  it. It may not re-judge, soften a failure, or add consequences the ruling did
  not authorise.

Splitting them keeps judgement auditable: the ruling is structured data that the
runtime can validate, while the prose is free.

## Who owns what

| Concern | Owner |
| --- | --- |
| Role, procedure, fairness rules, output contracts | `skills/storyteller/SKILL.md` |
| Canon: characters, places, loop rules, prohibitions | `skills/storyteller/world.md` |
| Opening scene, in both languages | `skills/storyteller/openings.json` |
| What a ruling is allowed to do to the session | `backend/session.py` |
| Prompt assembly, skill loading, phase calls | `backend/storyteller.py` |
| Model transport | `backend/model.py` |
| HTTP surface, sessions, error mapping | `backend/server.py` |
| Playable page, bilingual UI | `web/` |

The skill is not documentation for humans only: it is loaded at startup and sent
with every request. Editing the skill changes the Storyteller's behaviour without
touching Python.

## What the runtime enforces

The Storyteller decides; the runtime refuses what would break the story.

- A day holds six time units. The ruling prices each action in units (0–3), so a
  line of dialogue can cost nothing and a walk to the bridge can cost most of the
  day. When the day is spent, the loop advances to the next morning.
- On reset the crow's trust returns to zero because she keeps no memory of the
  previous day; the fox keeps its insight and the established facts.
- Deltas, facts, and time costs are clamped and deduplicated. An unusable ruling
  is rejected with `502`, and the session is left untouched.
- A declared ending is accepted only after at least eight judged turns, insight of
  at least 3, and crow trust of at least 3. Earlier claims are recorded as
  `loop_break_refused` and play continues. This floor stops a single turn from
  skipping the story; it does not replace the Storyteller's judgement.
- Input is one line: at most 400 characters, `say` or `do`. One turn is in flight
  per session (`409` otherwise), and a failed model call never advances time.

## Current limits

- Sessions live in process memory; a restart clears them.
- Continuity comes from eight recent turns plus established facts, not from a
  full narrative database.
- The page and the API are served by one standard-library process; there is no
  build step and no front-end framework.
- Passing tests describe implementation behaviour only. They say nothing about
  narrative quality, Agent capability, author utility, or research validity.
