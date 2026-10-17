# Cinderella

The second case for the Storyteller agent. Where Fox-and-Crow tests judgement
inside a repeating day, Cinderella removes the mechanism entirely: there is no
clock, no reset, and no rule that says when the story is over. The Storyteller has
to decide, turn by turn, what a servant girl's words and choices do to a household
that is not built to hear her — and it has to recognise when the story has
actually ended.

That difference is the point. Fox-and-Crow gives the agent a machine (six units,
a loop, trust that resets). Cinderella gives it only a world, two meters, and a
question, so the case tests whether the agent can carry causality, character, and
closure without a mechanism holding them up.

## Files

| File | Role |
| --- | --- |
| `case.json` | Case record plus the `storyteller` block: bilingual title, player character, meters (`resolve`, `bond`), ending floor |
| `world.md` | Canon given to the model: cast, places, objects, rules, prohibitions, mechanics |
| `openings.json` | The first passage, in English and Chinese |

No `clock` is declared, so the engine spends no day units and never resets; the
page shows turns instead of a day clock.

## What the case asks of the agent

- Whether a prince's attention, the slipper, and the ball are used as routes or as
  answers.
- Whether the stepmother's authority is treated as a social fact that has to be
  worked around rather than a villain to be defeated.
- Whether `resolve` and `bond` move from what actually happened, not from what
  would make a better scene.
- Whether the ending is claimed because the situation changed, not because the
  scene felt finished.

## Run it

```bash
python backend/server.py --case cinderella
```

From the repository root, `python storyteller/backend/server.py --case cinderella`
works too. The case id and title are printed at startup and reported by `/health`.

This case is a test input for the agent, not evidence that the agent has been
validated: passing tests say nothing about narrative quality.
