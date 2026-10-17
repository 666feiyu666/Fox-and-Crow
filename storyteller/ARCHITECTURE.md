# Engine architecture

`storyteller/` is an engine with no story of its own. A case in `cases/` supplies
the world, the opening, and the character; the engine supplies the two-phase
loop, the HTTP surface, and the page. One process plays one case.

```text
player line (say or do)
    -> POST /api/turn
    -> phase 1: storyteller rules on the action   (skill + case canon, session language)
    -> phase 2: storyteller narrates the ruling   (same prompt, same language)
    -> session.py records the turn and the facts the ruling declared
    -> narration, hints, turn number returned to the page
```

## The loop

Every story the engine plays is a loop, and the engine does not decide what
breaks it. The ruling may return `restart: true` — the turn only repeated the
story and the world comes round to its first morning — or `ending: true` — the
loop is broken and the story is over. Both are the storyteller's judgement,
informed by the case's canon; the runtime only counts loops, resets the turn
counter, and refuses further turns after an ending.

## Two phases, one judgement

- **Ruling** decides privately what the action changes: an outcome
  (`success`, `partial`, `failure`, `blocked`), a scene plan for the next phase,
  and any facts the turn fixes. The player never sees this object.
- **Narration** receives the ruling as final and writes the visible passage from
  it. It may not re-judge, soften a failure, or add consequences the ruling did
  not authorise.

Splitting them keeps judgement inspectable: the ruling is small structured data
the runtime can validate, while the prose stays free.

## Who owns what

| Concern | Owner |
| --- | --- |
| Role, procedure, fairness rules, output contracts | `skills/storyteller/SKILL.md` |
| Canon: cast, places, rules, prohibitions | `cases/<case>/world.<lang>.md` |
| Opening passage | `cases/<case>/opening.<lang>.md` |
| Title and player character | `cases/<case>/case.json` |
| Turn history and declared facts | `backend/session.py` |
| Prompt assembly and the two phase calls | `backend/storyteller.py` |
| Case loading and validation | `backend/case.py` |
| Model transport | `backend/model.py` |
| HTTP surface, sessions, error mapping | `backend/server.py` |
| Playable page, bilingual UI | `web/` |

The skill is loaded at startup and sent with every request, together with the
case's canon in the session language. Editing either changes what the storyteller
does without touching Python; editing a case's files changes one story only.

## What the runtime does

The runtime is deliberately thin. It does not decide outcomes, endings, or pacing.

- Rejects malformed rulings: an unknown `outcome`, a missing `scene`, or a
  narration without text is answered with `502`, and the session is untouched.
- Keeps the last eight turns and up to forty declared facts, which are the only
  memory the model is given besides the canon.
- Validates input: one line, at most 400 characters, `say` or `do`; one turn in
  flight per session (`409` otherwise).
- Maps model failures to `503`/`502` without advancing the story.

## Current limits

- Sessions live in process memory; a restart clears them.
- Continuity is eight turns plus declared facts, not a narrative database.
- One process serves one case; a different case means a different deployment.
- Passing tests describe implementation behaviour only. They say nothing about
  narrative quality, Agent capability, author utility, or research validity.
