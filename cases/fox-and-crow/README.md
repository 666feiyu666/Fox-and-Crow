# The Fox and the Crow

A playable story built on Aesop's fable. You are the fox: hungry, proud, and used
to getting what you want by talking. A crow sits above you with cheese in her
beak. There is something in the thorn bush she cannot reach, and a road out of the
forest that is not what it looks like.

Nothing is scripted. Every line you say or action you attempt is handed to the
storyteller, which decides what it changes out there and continues the story.

## The loop

This story is a loop. The same morning comes round again — the cheese back in the
crow's beak, the necklace back in the thorns, the bridge still broken — and only
the fox remembers having lived it.

Playing the fable the way the fable goes does not finish it. Get the cheese by
flattery, get it by force, fail at both: the day ends and the morning comes back.
The story ends only when the loop is broken, and breaking it is the storyteller's
judgement, not a rule printed here: the fox has to stop treating the crow as a
means, understand what she is actually carrying, and act on that. The page will
never tell you when you are close.

## What the case ships

- **The tale** — `source.en.md` / `source.zh.md`: Aesop's fable, retold in each
  language. This is the only authored story content.
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
python backend/server.py --case fox-and-crow
```

Then open `http://127.0.0.1:8000` and play. The language button in the top right
restarts the story in the other language.

## What this case is for

It is a test input for the storyteller agent: a small, well-known world where the
interesting variable is what the agent does with a player who refuses the fable's
usual trick. Passing tests say nothing about whether the story it tells is good.
