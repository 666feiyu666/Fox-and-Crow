# Engine architecture

A case provides its title and original tale in each supported language. The same
three skills work for every case; no plot, object name, character or ending is
hard-coded in the engine. One process serves one case.

## Preparation

The preparation graph is:

```text
START -> understand -> write_opening -> END
```

The understander returns player, canon, an opening seed and a structured space:

| Field | Meaning |
| --- | --- |
| anchors | Source-grounded claims with exact excerpts from this case's tale |
| situation | The point of divergence and independent pressures already present |
| initial_facts | Keyed current properties and the actors who know their values |
| fixed_keys | Initial properties that actual world rules make unchangeable |
| possibilities | Uncommitted avenues of action and questions, never current facts |
| adaptation | Authored loop, reset and ending principles, distinguished from the source |
| style | Public writing voice without hidden goals, solutions or future reveals |

Canon labels source material, inferences and adaptation. An exact quotation is
checked against the source; the program does not verify that the quote logically
entails the model's interpretation. Initial facts may include fixed secrets; gaps
remain open for later completion. Characterization informs play without deciding
the player's new intentions.

The writer renders the opening seed using the same craft resource as turns.
Preparation completes only when the space and the written opening both succeed.
The result is cached in `cases/<case>/.generated/understanding.<lang>.json`.

Schema version 2 invalidates older readings. The cache fingerprint covers the
source, language, preparation and writer skills (including loaded craft), task
instructions, model id and endpoint. Restart the process to load edited files.
A compatible cached reading is reused without model calls. Preparation costs two
calls when needed, and each ordinary turn costs two.

## A turn

```text
player action
  -> judge: current world + source-grounded space + recent play
  -> validate proposal and project its consequences (no mutation)
  -> writer: visible projection + perceptible events + brief + voice
  -> validate narration
  -> commit state, knowledge, memory and complete ruling together
  -> return passage, optional hints and public status
```

The judge can settle relevant undecided details as expansions. It can accept
unanticipated methods, follow NPC goals, let a player refuse the original aim,
and judge different trajectories. It must not make a fixed secret move or invent
a restriction just to force a route.

The ruling carries intent, outcome, observed/offscreen events, expansions,
changes, observations, optional memory notes, a writing brief and loop flags.

- **expansions** establish new background properties under new keys. They persist
  across loops. Their initial known_by is empty; discoveries use observations.
- **changes** replace current property values under stable keys for this loop.
  Their known_by describes knowledge of the new value, not an obsolete one.
- **observations** grant an actor knowledge of a current or newly proposed fact.
- **events** say what happened and who perceived it. Offscreen events remain in
  the private audit; experienced events become loop-tagged player memories.
- **brief** supplies visible material, focus, suggested prose mode, uncertainty
  and the next decision before which writing stops.

Duplicate update keys, redefined expansions, changed fixed properties, absent
observation targets, incompatible loop flags/modes and incomplete proposals are
rejected before the turn writer is called. Oversized structured data is rejected
rather than silently cut. These are structural and keyed consistency guarantees;
natural-language causality and fair interpretation remain model responsibilities.

## State and knowledge

StoryState keeps the initial snapshot, persistent completions, loop-local
overrides, loop-tagged player memories, and the full private turn audit. Current
facts merge by key, so an object has one current holder instead of accumulating
contradictory holder sentences. Fixed properties cannot acquire a different value
through a change.

A restart discards loop-local actions and knowledge overlays, restores initial
facts and retains persistent world completions and the player's memories. NPCs
therefore do not retain discoveries from an earlier loop. Old event memories
remain history with an explicit loop number.

A memory reference has up to eight recent passages, plus established current facts
and retained player memories. The full audit is kept in process memory; the model
does not receive every private past ruling. There is no disk-backed session log,
retrieval index or long-session memory compression yet.

## The writer's boundary

The writer receives no full canon, private possibilities or hidden fact table.
Its prompt contains the role, language and public style. Its input contains only
player-known projected facts, witnessed events, player memories, the opening,
recent visible play and a player-visible brief. A restart projects the reset
world for writing, rather than the obsolete pre-reset object state.

The judge still has to respect visibility when composing the free-text brief.
Filtering structured facts is not a semantic proof that a brief, style reference
or generated passage cannot leak information.

The writer chooses concrete language, dialogue delivery, sensory texture and
rhythm. A new promise, usable object, revelation or relationship change requires
an authorised event or fact. Modes are direct, dialogue, action, transition,
return and ending; they are presentation guidance. Hints are optional.

`skills/writer/references/craft.md` is explicitly loaded by case.py and appended to
the writer skill. A Markdown link alone does not load a resource into the API
model. Both openings and turn passages use that loaded craft.

## Generality, language and limits

Existing and future cases use the same contracts. A new case requires case.json
and source.en.md/source.zh.md; preparation derives its own cast, world and voice.
Looping remains this project's shared adaptation convention, without a fixed
moral solution in Python.

Each language currently receives a separate preparation. This preserves the
supplied source wording but does not guarantee identical interpretations between
languages; cross-language equivalence remains a separate evaluation task.

The HTTP surface retains language/loop/turn/ended status and narration/hints.
Model or validation failure leaves the committed session untouched. Sessions
remain process-local, and process restart clears them. Passing offline tests
establishes implementation behavior, not prose quality, player agency or research
validity.
