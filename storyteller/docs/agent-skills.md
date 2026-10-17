# The four agent skills

The runtime prepares a story space, responds to play and renders the response.
These responsibilities use the same four skills for every case.

| Skill | Responsibility |
| --- | --- |
| skills/understand/SKILL.md | Source evidence, initial situation, open possibilities, adaptation and voice |
| skills/judge/SKILL.md | Resolve the attempt, complete relevant gaps, propose events and state changes |
| skills/writer/SKILL.md | Render an opening or a turn from visible material and writing craft |
| skills/reader-review/SKILL.md | Review content quality and direction; pass or request a targeted repair |

The preparation graph runs understand then write_opening, which renders and reviews
the opening. The turn graph runs judge, write, then review with conditional repair
edges. Preparation normally costs three calls and is cached; a normal turn costs
three. Writing the opening reuses the writer skill.

## Imagination and commitment

The understander imagines uses, conflicts and alternative intentions, while
keeping them in possibilities. These do not become current facts or mandatory
story beats. Source claims carry exact original quotations. Inferences and
adaptation are labelled separately in canon; the loop is an authored convention.

The judge considers the player's actual attempt. It may establish a relevant
undecided world detail through an expansion. It must record that detail and keep
it stable thereafter. An already fixed secret is not an undecided gap.

Initial facts and updates use stable property keys. The program rejects an
expansion that redefines an existing key and an update that changes a fixed
property. It cannot recognise every contradiction expressed under unrelated keys,
nor determine from prose alone whether an NPC response is fair.

The original plot supplies a prior trajectory. Refusals, exchanges, departures and
novel methods can have their own consequences. The player retains control of
their choices, present motives and dialogue.

## Writer context and craft

A turn brief specifies focus, mode, visible results, remaining uncertainty and a
stopping point before the next player decision. The judge determines consequences,
leaving wording, dialogue delivery, narrative attention and rhythm to the writer.

The writer receives projected player-known facts and witnessed events, not the
private world document. The judge must keep its brief visible too. New useful
objects, promises, revelations or relationship changes require authorisation;
ordinary texture can be written freely within those bounds.

Modes are guidance, not fixed paragraph structures. A routine action can receive
one sentence, an exchange can take more room, and uneventful time can be compressed.
Hints can be empty, and endings should have none.

The runtime explicitly loads skills/writer/references/craft.md. Referenced files
do not load themselves in an API call. If this resource changes, the preparation
fingerprint changes too, so future process starts regenerate the opening.

## Reader-Review

This skill performs editorial diagnosis using canon, the prepared space, current
and projected facts, ruling and candidate text/hints. It checks content direction,
coherence, writing and presentation, without trying to measure player satisfaction,
agency, challenge or playability. It does not pretend to be unaware of its context.

pass may include non-blocking suggestions. revise requires a concrete blocking
finding and an owner: writer when the ruling stands, judge when events, character
reaction or causal reasoning must change. The report identifies the passage or
property, evidence, effect and requested direction, while preserving strengths.
It does not supply replacement prose or an alternative plot.

One directed revision is allowed, followed by another review. A second rejection
or unusable report leaves the committed state untouched. Judge repairs see the
full report; writer repairs receive only public editorial requests and preserve
notes. Internal review evidence is not forwarded into the writer's context.
Only accepted final events enter facts and memories. The private turn audit keeps
the candidate/review history; published text and hints never include that history.

Openings also pass this gate before caching. Presentation can be rewritten once;
a contradiction in the prepared space stops preparation for inspection.

## Design references

The runtime instructions and craft resource were written for this project's
player/agent boundary. Their design draws on these resources in
[haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills)
(Apache-2.0), inspected on 2026-10-17:

- [Brainstorming capture](https://github.com/haowjy/creative-writing-skills/blob/main/skills/story-planning/resources/brainstorming.md):
  distinguish settled information, suggestions and unresolved questions.
- [Story context](https://github.com/haowjy/creative-writing-skills/blob/main/skills/story-memory/resources/story-context.md):
  hand writers a scoped brief, style, character state and continuity anchors.
- [Scene construction](https://github.com/haowjy/creative-writing-skills/blob/main/skills/creative-writing-craft/resources/scene-construction.md):
  dialogue, subtext and changing scene rhythm.
- [Failure modes](https://github.com/haowjy/creative-writing-skills/blob/main/skills/writing-principles/resources/failure-modes.md):
  voice uniformity, stock gestures, premature resolution and over-explanation.
- [Story review](https://github.com/haowjy/creative-writing-skills/blob/main/skills/story-review/SKILL.md)
  and [editorial review](https://github.com/haowjy/creative-writing-skills/blob/main/skills/story-review/resources/editorial-review.md):
  diagnose the level and cost of a problem while protecting the story's voice.
  This runtime adds bounded feedback to judge/writer rather than manuscript editing.

The upstream author-facing routing, agent orchestration and manuscript workflows
are not runtime dependencies. No package installation or network fetch is needed
to load this project's craft resource.

## Editing and verification

Edit a case's sources for its material, understand for preparation, judge for world
response, writer/craft for presentation, and reader-review for content diagnosis.
The full contracts are in the skills and backend/space.py, backend/review.py,
backend/understanding.py and backend/session.py. See
../ARCHITECTURE.md for state, knowledge and cache behavior.

Restart the process after edits. The cache schema and input fingerprint reject
old incompatible readings automatically. Compatible generated JSON remains
reviewable; preserve the source anchors and structured fields when editing it.

Offline tests cover both existing cases in both languages, a new temporary case,
persistent completions, mutable properties, knowledge filtering, restart, cache
invalidation, editorial repair routing, privacy of review feedback and failed-turn
rollback. They use stub model responses and cannot
establish the literary or playable quality of these instructions.
