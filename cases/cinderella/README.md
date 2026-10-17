# Cinderella

A playable story built on the Perrault tale. You are Cinderella: the work of the
house is yours, the comfort of it is not, and the palace has just announced a ball.
There is a godmother who can give you one evening, a stepmother who will not simply
be told no, and a prince who has never had a reason to look past a dress.

Nothing is scripted. Every line you say or action you attempt is handed to the
storyteller, which decides what it changes in that house and at that court, and
continues the story.

## The loop

This story is a loop. The day comes round again — the invitation on the table, the
ash still damp, the slipper never having existed — and only Cinderella remembers
having lived it.

Playing the tale the way the tale goes does not finish it. Let the godmother dress
you, dance until midnight, run, be found by the slipper: the day ends and the
morning comes back. The story ends only when the loop is broken, and breaking it is
the storyteller's judgement, not a rule printed here: Cinderella has to change her
situation by her own action and be known as a person rather than a shoe size. The
page will never tell you when you are close.

## What the case ships

- **The tale** — `source.en.md` / `source.zh.md`: the Perrault story, retold in
  each language. This is the only authored story content.
- **Id and title** — `case.json`.

The player's role, the world canon, and the opening passage are not written here.
The understander derives them from the tale on first use and caches them in
`.generated/`, where you can read them, correct them, or delete them to force a
fresh reading.

## Files

| File | Purpose |
| --- | --- |
| `case.json` | Story id and bilingual title |
| `source.en.md`, `source.zh.md` | The original tale, the only thing the agents read |
| `.generated/` | Derived player, canon, and opening (created on first run) |

## Run it

```bash
cd storyteller
python backend/server.py --case cinderella
```

Then open `http://127.0.0.1:8000`, choose the story on the shelf, and pick the
language it is told in. That choice holds for the whole run; starting another run
from the shelf lets you pick again.

## What this case is for

It is a test input for the storyteller agent: a world where the obvious rescue is
available and the interesting question is whether the agent lets Cinderella earn
something better. Passing tests say nothing about whether the story it tells is
good.
