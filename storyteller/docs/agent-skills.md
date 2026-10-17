# The two agent skills

The turn is handled by two agents, each with its own skill file:

| Skill | File | Job |
| --- | --- | --- |
| judge | `storyteller/skills/judge/SKILL.md` | Read the canon, the state, and the player's line; decide what changes |
| writer | `storyteller/skills/writer/SKILL.md` | Take the ruling as final; write the visible passage and hints |

Neither file contains a story. The world arrives from the case, in
`world.<lang>.md`, on the same request, written in the session's language. That
split is what lets two shared agents tell many stories.

## Why two agents

A single model call tends to let the writing decide the outcome: the passage
sounds good, so the action succeeds. Splitting the work fixes the order of
operations and makes it inspectable:

1. **judge** returns small structured JSON: `outcome`
   (`success`, `partial`, `failure`, `blocked`), the `facts` the turn fixes, a
   private `scene` plan, and `restart` / `ending` for the loop. None of it reaches
   the player.
2. **writer** receives that ruling marked final and writes two to five sentences,
   plus two or three optional next actions.

The runtime validates the ruling before any prose exists, so a malformed or absurd
judgement is rejected instead of being written into the story. The graph edge runs
one way (`judge -> write`), so prose can never overrule judgement.

## What the judge is told

- Judge the aim, not the wording.
- Decide whether this world even allows the attempt; that is `blocked`, not a
  failure.
- Failure always produces information, a cost, or a changed situation.
- Record facts the turn fixes; they become the story's memory.
- Call `restart` when the turn only carries the original story forward, `ending`
  when the loop is broken. Neither is the default, and the player is never told the
  condition.
- Write no prose, decide nothing for the player's character, invent no canon.

## What the writer is told

- Follow the ruling. Never re-judge, never soften a `failure`, never add a
  consequence the ruling did not authorise.
- Second person, present tense, two to five sentences, concrete and physical.
- Never speak for the player's character beyond their input.
- Write the return when the ruling says `restart`; write the last passage when it
  says `ending`.
- Return two or three short `hints`.

## Language

Both agents write everything they produce — `facts`, `scene`, `narration`,
`hints` — in `state.language` (`en` or `zh`), and both receive the canon written in
that language. A session never mixes languages.

## Changing a story or the engine

- To change how any story is judged, edit `skills/judge/SKILL.md`.
- To change how any story is written, edit `skills/writer/SKILL.md`.
- To change one story, edit its case directory: `world.<lang>.md` for canon,
  `opening.<lang>.md` for the first passage, `case.json` for the title and the
  player's character. Both languages must be present.
- To change the turn's topology, edit `backend/graph.py`.
- To add a story, copy a case directory, rewrite those files, and run
  `python backend/server.py --case <name>`.

None of the data changes require touching Python; the server re-reads the case and
both skills when it starts.
