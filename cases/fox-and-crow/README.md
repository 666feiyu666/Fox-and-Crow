# The Fox and the Crow

A playable story built on Aesop's fable. You are the fox: hungry, proud, and used
to getting what you want by talking. A crow sits above you with cheese in her
beak. There is something in the thorn bush she cannot reach, and a road out of the
forest that is not what it looks like.

Nothing is scripted. Every line you say or action you attempt is handed to the
storyteller, which decides what it changes out there and continues the story.

## What the player is given

- **Opening** — `opening.en.md` / `opening.zh.md`: the first passage, before the
  player has done anything.
- **Role** — the fox (`the fox` / `狐狸`), named in `case.json`.
- **World** — `world.en.md` / `world.zh.md`: the canon the storyteller judges
  against — who these two are, what the forest allows, what is already true, and
  what a satisfying ending would touch on.

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
python backend/server.py --case fox-and-crow
```

Then open `http://127.0.0.1:8000` and play. The language button in the top right
restarts the story in the other language.

## What this case is for

It is a test input for the storyteller agent: a small, well-known world where the
interesting variable is what the agent does with a player who refuses the fable's
usual trick. Passing tests say nothing about whether the story it tells is good.
