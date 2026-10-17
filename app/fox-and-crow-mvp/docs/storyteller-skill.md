# The Storyteller skill

`skills/storyteller/` is the agent. It has three files, and all three are sent to
the model on every request.

| File | Role |
| --- | --- |
| `SKILL.md` | Who the Storyteller is, how it rules, what it must never do, and the JSON contract for both phases |
| `world.md` | Canon: cast, places, objects, loop rules, fixed facts, prohibitions |
| `openings.json` | The first passage the player reads, in English and Chinese |

## The role

The Storyteller is an omniscient dungeon master, not a narrator who follows the
player. It knows the crow's goal, the necklace in the thorns, the broken bridge,
and why the day keeps returning. The player speaks and acts only as the fox.

That asymmetry is the design: the player has one limited viewpoint, and the
Storyteller decides what that viewpoint can change. The player proposes; the
Storyteller disposes.

## Why two phases

A single model call tends to let the writing decide the outcome: the passage
sounds good, so the action succeeds. Separating the calls makes judgement explicit
and inspectable:

1. **Ruling** — the Storyteller answers in structured JSON: `outcome`
   (`success`, `partial`, `failure`, `blocked`), `time_cost` (0–3 of six daily
   units), `trust` and `insight` deltas, new `facts`, a private `scene` plan, and
   `ending`. Nothing of this reaches the player.
2. **Narration** — a second call receives the ruling marked final and writes two
   to four sentences in the session language, plus two or three optional next
   actions.

The runtime validates the ruling before any prose exists, so a malformed or
absurd judgement is rejected instead of being written into the story.

## The judging procedure

`SKILL.md` fixes nine steps, in order: intent, permission, outcome, price,
relationship, understanding, facts, scene, ending. Two of them carry most of the
design weight:

- **Permission** asks whether the world allows the attempt at all. The fox cannot
  climb the high branch, cannot know what it has not observed, cannot leave while
  the bridge is down. This is where the world canon blocks convenient invention.
- **Price** makes time a consequence rather than a clock. Because the Storyteller
  prices each action, a conversation can leave the day almost intact while a
  failed climb burns it.

## State the Storyteller may not invent

The Storyteller knows the crow's trust and the fox's insight as true numbers, and
sees only the last eight turns plus the established facts. It proposes deltas; the
runtime clamps them and owns the totals, the day, the loop, and the ending.

Three rules are the runtime's, not the skill's:

- Time resets after six units, and the crow's trust resets with it.
- Facts accumulate and are never silently contradicted.
- The loop cannot end before eight judged turns, insight 3, and trust 3.

They are written down in `ARCHITECTURE.md` so a reader can tell which guarantees
are prompt-level and which are code-level.

## Language

`narration` and `hints` follow `state.language` (`en` or `zh`). `scene` and `facts`
stay in English because they are working notes for the next phase and the next
turn, not text the player reads.

## Changing the story

- To change behaviour, edit `SKILL.md`.
- To change canon, edit `world.md`.
- To change the opening page, edit `openings.json`.
- To change what the runtime guarantees, edit `backend/session.py` and its tests.

None of the first three require a code change or a restart of the browser page;
the skill is re-read when the server starts.
