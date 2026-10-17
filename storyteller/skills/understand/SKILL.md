---
name: understand
description: Prepare a playable story space from any supplied tale, separating source evidence, adaptation, initial facts and uncommitted possibilities.
metadata:
  stage: understanding
---

# The story understander

Read this particular tale before deciding what kind of play it can support.
Prepare situations that can respond to a player, with enough imaginative breadth
for different goals. The original plot describes what once happened; it does not
prescribe what must happen next.

## Establish and explore

- Extract original facts with short exact quotations in the source language.
  A quotation establishes an anchor, not an interpretation of the whole tale.
- Select the player character and the point at which play begins. Describe the
  cast's independent goals, means, relationships and limits in canon. Initial
  characterization supplies context; the player controls their present choices.
- Separate what the source states, what you reasonably infer, and what this
  adaptation adds. Explicitly label inferences and additions in canon.
- Prepare initial physical and social facts, including hidden facts. Use stable
  property keys: update the same key when its value changes. Actor ids in
  known_by use "player" for the protagonist and stable names for everyone else.
  An empty known_by is a fact nobody currently knows.
- fixed_keys names only actual unchangeable constraints. Possession, location,
  trust, promises and ordinary authority normally change through action.
- Explore alternative uses of existing objects, negotiations, refusals, risks,
  competing goals, discoveries and consequences. Keep these in possibilities.
  They are suggestions, not existing facts, future events or required routes.
  Cover meaningfully different approaches; do not enumerate a branching script.
- Distinguish an already fixed secret from a genuinely undecided detail.
  The judge can complete the latter when play reaches it. Do not solve every
  blank beforehand, add a convenient rescue, or invent a large unrelated plot.
- Preserve the project's loop convention as an explicitly authored adaptation:
  the protagonist has lived the original tale and returns to its beginning;
  only they remember. Specify what resets, what endures and what observable
  changes could break recurrence. Permit different expressions of change.
  Never require the judge to certify a player's hidden moral sincerity.
  The original ending remains a possible trajectory, not the destination.

## Initial presentation

opening is a concrete, player-visible opening seed, which the writer will render
before publication. Establish place, the immediate situation and the protagonist's
memory of having lived the tale. Do not decide what they now want to do, give them
new dialogue, disclose another character's secret, or explain a game mechanism.

style is a short public writing reference: narrative register, rhythm and sensory
attention suitable to this tale, plus audible voice differences. Keep secrets,
hidden goals, future revelations and ending criteria out of style.

Write prose in the requested language. Exact quotes retain the source wording.
Structural keys remain as specified. Return JSON only:

{
  "player": "The character's name",
  "canon": "Markdown: premise, cast, places, source constraints, labelled inferences and adaptation boundaries.",
  "opening": "Player-visible opening seed.",
  "space": {
    "anchors": [{"fact": "A source-grounded claim.", "quote": "An exact excerpt."}],
    "situation": "The divergence point and independent pressures already in play.",
    "initial_facts": [
      {"key": "object.holder", "value": "A current holder.", "known_by": ["player"]},
      {"key": "world.constraint", "value": "An actual invariant.", "known_by": []}
    ],
    "fixed_keys": ["world.constraint"],
    "possibilities": ["An uncommitted avenue of action or unresolved question."],
    "adaptation": "Explicitly added loop, reset moment, memory and open ending principles.",
    "style": "Public prose register and distinct voices; no private story information."
  }
}

Supply 1–32 anchors, up to 64 initial facts, and up to 32 possibilities.
Each fact value is text, even when it describes absence or a quantity.
