# Engine architecture

`storyteller/` is an engine with no story of its own. A case in `cases/` supplies
only the original tale; the engine derives the rest and then runs the turns, all
as LangGraph graphs. One process plays one case.

```text
first session in a language
    -> LangGraph: understand
         understand   original tale -> player + canon + opening (cached beside the case)

player line (say or do)
    -> POST /api/turn
    -> LangGraph: judge -> write
         judge   canon + state + action -> ruling JSON      (no prose)
         write   canon + ruling         -> narration + hints (no verdicts)
    -> session.py records the turn and the facts the ruling declared
    -> narration, hints, loop and turn returned to the page
```

## Three agents, two graphs

`backend/graph.py` compiles two LangGraph `StateGraph`s.

**Understanding** — `START -> understand -> END`:

- **understand** — its own skill, `skills/understand/SKILL.md`. It reads the tale
  and returns the player's role, the world canon, and the opening passage. The
  result is validated, fingerprinted against the tale, and cached at
  `cases/<case>/.generated/understanding.<lang>.json`.

**The turn** — `START -> judge -> write -> END`:

- **judge** — its own skill, `skills/judge/SKILL.md`. It reads the derived canon,
  the state, and the player's line, and returns the ruling: outcome, facts, a
  private scene plan, and whether the turn restarts or ends the loop. It writes no
  prose.
- **write** — its own skill, `skills/writer/SKILL.md`. It receives the ruling as
  final and writes the visible passage and hints. It makes no verdicts.

The edge runs one way only, so prose can never overrule judgement. The understander
runs once per language: the cache is keyed by a digest of the tale, so an edited
tale regenerates it and nothing stale survives.

## The loop

Every story the engine plays is a loop, and the engine does not decide what breaks
it. The ruling may return `restart: true` — the turn only repeated the story and
the world comes round to its first morning — or `ending: true` — the loop is broken
and the story is over. Both are the judge's decision, informed by the derived
canon; the runtime only counts loops, resets the turn counter, and refuses further
turns after an ending.

## Who owns what

| Concern | Owner |
| --- | --- |
| Derivation rules: what to take from a tale | `skills/understand/SKILL.md` |
| Judgement rules and the ruling contract | `skills/judge/SKILL.md` |
| Narrative craft and the narration contract | `skills/writer/SKILL.md` |
| Graph topologies and node wiring | `backend/graph.py` |
| The derived player, canon, opening, and its cache | `backend/understanding.py` |
| The original tale | `cases/<case>/source.<lang>.md` |
| Story id and title | `cases/<case>/case.json` |
| Turn history and declared facts | `backend/session.py` |
| Prompt assembly and the agent calls | `backend/storyteller.py` |
| Case loading and validation | `backend/case.py` |
| Model transport | `backend/model.py` |
| HTTP surface, sessions, error mapping | `backend/server.py` |
| Playable page, bilingual UI | `web/` |

The skills are loaded at startup and sent with every request. Editing a skill
changes one agent's behaviour; editing a case's tale changes one story, and the
understanding is derived again from it.

## What the runtime does

The runtime is deliberately thin. It does not decide outcomes, endings, or pacing.

- Derives the case once per language, caches it beside the case, and regenerates it
  when the tale's digest changes.
- Rejects malformed output: an unknown `outcome`, a missing `scene`, a narration
  without text, a ruling that both restarts and ends, or an understanding missing
  its player, canon, or opening is answered with `502`, and no state moves.
- Keeps the last eight turns and up to forty declared facts, which are the only
  memory the agents are given besides the canon.
- Validates input: one line, at most 400 characters, `say` or `do`; one turn in
  flight per session (`409` otherwise).
- Maps model failures to `503`/`502` without advancing the story.

## Current limits

- Sessions live in process memory; a restart clears them.
- Continuity is eight turns plus declared facts, not a narrative database.
- The deriver is an LLM: two runs over the same tale can differ. The cache is what
  makes a run stable, and the cached JSON is meant to be reviewed and edited.
- One process serves one case; a different case means a different deployment.
- Passing tests describe implementation behaviour only. They say nothing about
  narrative quality, Agent capability, author utility, or research validity.
