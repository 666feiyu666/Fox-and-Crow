# The Storyteller skill

`storyteller/skills/storyteller/SKILL.md` is the agent: one file, loaded at
startup and sent with every request. It describes a Storyteller who is
story-independent — an omniscient dungeon master who judges an action against the
world it is given.

The world itself is not in the skill. It arrives from the case, in `world.md`,
on the same request. That split is what makes one agent play many stories.

## The role

The Storyteller is an omniscient dungeon master, not a narrator who follows the
player. It knows what the case's canon says about everyone's goals, secrets, and
limits. The player speaks and acts only as one character.

That asymmetry is the design: the player has one limited viewpoint, and the
Storyteller decides what that viewpoint can change. The player proposes; the
Storyteller disposes.

## Why two phases

A single model call tends to let the writing decide the outcome: the passage
sounds good, so the action succeeds. Separating the calls makes judgement explicit
and inspectable:

1. **Ruling** — the Storyteller answers in structured JSON: `outcome`
   (`success`, `partial`, `failure`, `blocked`), `time_cost` (0–3 units when the
   case has a clock), `meters` (deltas for the meters the case declares), new
   `facts`, a private `scene` plan, and `ending`. None of it reaches the player.
2. **Narration** — a second call receives the ruling marked final and writes two
   to four sentences in the session language, plus two or three optional next
   actions.

The runtime validates the ruling before any prose exists, so a malformed or
absurd judgement is rejected instead of being written into the story.

## The judging procedure

`SKILL.md` fixes nine steps, in order: intent, permission, outcome, price,
meters, facts, scene, ending. Three carry most of the design weight:

- **Permission** asks whether the world allows the attempt at all. What the
  character cannot physically do, cannot know, or cannot reach is refused here.
- **Price** makes time a consequence rather than a clock, in the cases that have
  a clock at all.
- **Meters** are named by the state, not by the model. A ruling may move only the
  meters the case declares, by at most 2 per turn.

## State the Storyteller may not invent

The Storyteller sees the current meters as true numbers, the last eight turns, and
the established facts. It proposes deltas; the runtime clamps them and owns the
totals, the clock, the loop, and the ending.

Three rules are the runtime's, not the skill's:

- Meter ranges and per-turn limits come from `case.json`.
- A declared ending is refused until the case's turn floor and meter thresholds
  are met.
- Facts accumulate and are never silently contradicted.

They are written down in `ARCHITECTURE.md` so a reader can tell which guarantees
are prompt-level and which are code-level.

## Language

`narration` and `hints` follow `state.language` (`en` or `zh`). `scene` and `facts`
stay in English because they are working notes for the next phase and the next
turn, not text the player reads.

## Changing a story or the engine

- To change how any story is judged, edit `storyteller/skills/storyteller/SKILL.md`.
- To change one story's canon or mechanics, edit files under its case directory:
  `world.md` for canon, `case.json` for meters, clock, ending floor, and titles,
  `openings.json` for the first passage.
- To add a story, copy a case directory, rewrite those three files, and run
  `python backend/server.py --case <name>`.
- To change what the runtime guarantees, edit `backend/session.py` and its tests.

None of the data changes require touching Python; the server re-reads the case
when it starts.
