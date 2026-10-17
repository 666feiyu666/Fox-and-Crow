# The three agent skills

A turn is handled by two agents, and the case they work on is derived by a third:

| Agent | File | Job |
| --- | --- | --- |
| understand | `storyteller/skills/understand/SKILL.md` | Read the original tale; derive the player's role, the canon, and the opening |
| judge | `storyteller/skills/judge/SKILL.md` | Read the derived canon and the player's line; decide what changes |
| writer | `storyteller/skills/writer/SKILL.md` | Take the ruling as final; write the visible passage and hints |

None of the files contains a story. The tale arrives from the case as
`source.<lang>.md`; the understander turns it into a canon; the judge and the
writer work from that canon. That split is what lets shared agents tell many
stories.

## Why three

- **Understanding first** means a case is a story, not a configuration. Nothing
  about the world, the protagonist, or the opening has to be written by hand: the
  case ships the tale, and the agents read it. The result is cached under
  `cases/<case>/.generated/`, so it can be reviewed, corrected, and reused.
- **Judging before writing** means the prose cannot decide the outcome. The judge
  returns small structured JSON (an outcome, the facts the turn fixes, a private
  scene plan, and `restart` / `ending`). The writer receives it as final.
- The runtime validates both, so a malformed judgement is rejected before any prose
  exists, and prose can never overrule judgement.

## What the understander is told

- Read the tale in the language you are given and write in that language.
- Derive: the player's character, a canon in Markdown (premise, cast, places,
  objects, fixed facts, rules, **the loop**, prohibitions), and the opening passage.
- The story is a loop; name what it returns to, what walking the original tale
  forward looks like, and what kind of change would break it — in terms of what the
  protagonist must understand, never as a checklist.
- The opening shows a character who has already lived the tale once and has just
  come back to where it starts; show that through their own mind, never by
  explaining a mechanism.

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

Every agent writes in `state.language` (`en` or `zh`) and is given the tale and the
canon in that language. A session never mixes languages.

## Changing a story or the engine

- To change what is taken from a tale, edit `skills/understand/SKILL.md`.
- To change how any story is judged, edit `skills/judge/SKILL.md`.
- To change how any story is written, edit `skills/writer/SKILL.md`.
- To change a story, edit its `source.<lang>.md` (the tale) or its `case.json`
  (id and title). Both languages must be present. Delete
  `cases/<case>/.generated/` to force a fresh derivation.
- To change the graphs, edit `backend/graph.py`.
- To add a story, copy a case directory, replace the tale, and run
  `python backend/server.py --case <name>`.

None of the data changes require touching Python; the server re-reads the case and
all three skills when it starts.
