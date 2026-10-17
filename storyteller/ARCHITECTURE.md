# Engine architecture

`storyteller/` is an engine with no story of its own. A case in `cases/` supplies
the world, the opening, and the character; the engine supplies two agents wired as
a graph, the HTTP surface, and the page. One process plays one case.

```text
player line (say or do)
    -> POST /api/turn
    -> LangGraph: judge -> write
         judge   canon + state + action -> ruling JSON   (no prose)
         write   canon + ruling         -> narration + hints (no verdicts)
    -> session.py records the turn and the facts the ruling declared
    -> narration, hints, loop and turn returned to the page
```

## Two agents, one graph

`backend/graph.py` compiles a LangGraph `StateGraph` with two nodes:

- **judge** — its own skill, `skills/judge/SKILL.md`. It reads the canon, the
  current state, and the player's line, and returns the ruling: outcome, facts, a
  private scene plan, and whether the turn restarts or ends the loop. It writes no
  prose.
- **write** — its own skill, `skills/writer/SKILL.md`. It receives the ruling as
  final and writes the visible passage and the hints. It makes no verdicts.

The edge runs one way only — `START -> judge -> write -> END` — so the prose can
never overrule the judgement underneath it. Each agent gets its own prompt; both
are given the same canon in the session language.

## The loop

Every story the engine plays is a loop, and the engine does not decide what
breaks it. The ruling may return `restart: true` — the turn only repeated the
story and the world comes round to its first morning — or `ending: true` — the
loop is broken and the story is over. Both are the judge's decision, informed by
the case's canon; the runtime only counts loops, resets the turn counter, and
refuses further turns after an ending.

## Who owns what

| Concern | Owner |
| --- | --- |
| Judgement rules and the ruling contract | `skills/judge/SKILL.md` |
| Narrative craft and the narration contract | `skills/writer/SKILL.md` |
| Graph topology and node wiring | `backend/graph.py` |
| Canon: cast, places, rules, prohibitions | `cases/<case>/world.<lang>.md` |
| Opening passage | `cases/<case>/opening.<lang>.md` |
| Title and player character | `cases/<case>/case.json` |
| Turn history and declared facts | `backend/session.py` |
| Prompt assembly and the two agent calls | `backend/storyteller.py` |
| Case loading and validation | `backend/case.py` |
| Model transport | `backend/model.py` |
| HTTP surface, sessions, error mapping | `backend/server.py` |
| Playable page, bilingual UI | `web/` |

The skills are loaded at startup and sent with every request, each alongside the
case's canon in the session language. Editing a skill changes the agent's
behaviour; editing a case's files changes one story only.

## What the runtime does

The runtime is deliberately thin. It does not decide outcomes, endings, or pacing.

- Rejects malformed output: an unknown `outcome`, a missing `scene`, a narration
  without text, or a ruling that both restarts and ends is answered with `502`,
  and the session is untouched.
- Keeps the last eight turns and up to forty declared facts, which are the only
  memory the agents are given besides the canon.
- Validates input: one line, at most 400 characters, `say` or `do`; one turn in
  flight per session (`409` otherwise).
- Maps model failures to `503`/`502` without advancing the story.

## Current limits

- Sessions live in process memory; a restart clears them.
- Continuity is eight turns plus declared facts, not a narrative database.
- One process serves one case; a different case means a different deployment.
- Passing tests describe implementation behaviour only. They say nothing about
  narrative quality, Agent capability, author utility, or research validity.
