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

## What the player is given

- **Opening** — `opening.en.md` / `opening.zh.md`: the first passage, before the
  player has done anything.
- **Role** — Cinderella (`Cinderella` / `灰姑娘`), named in `case.json`.
- **World** — `world.en.md` / `world.zh.md`: the canon the storyteller judges
  against — the household, the palace, the magic and its midnight limit, what is
  already true, and what a satisfying ending would touch on.

## Files

| File | Purpose |
| --- | --- |
| `case.json` | Story id, bilingual title, and the character the player plays |
| `world.en.md`, `world.zh.md` | The same canon written in each language |
| `opening.en.md`, `opening.zh.md` | The first passage in each language |

Every file exists in both languages, and a session picks one: the opening,
narration, hints, and the storyteller's own notes are all written in that
language, with no mixing.

## Run it

```bash
cd storyteller
python backend/server.py --case cinderella
```

Then open `http://127.0.0.1:8000` and play. The language button in the top right
restarts the story in the other language.

## What this case is for

It is a test input for the storyteller agent: a world where the obvious rescue is
available and the interesting question is whether the agent lets Cinderella earn
something better. Passing tests say nothing about whether the story it tells is
good.
