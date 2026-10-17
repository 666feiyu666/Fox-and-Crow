# Storyteller

A small engine for playable stories told by a generative LLM agent. The player is
given an opening passage and a character; they write one line or one action at a
time; the storyteller decides what that changes in the world and continues the
story. There is no branching script, no build step, and no rulebook the engine
enforces on top of the world the case describes.

```text
storyteller/
├── skills/storyteller/SKILL.md   the agent: role, procedure, output contracts
├── backend/                      case loading, story state, two-phase agent, HTTP
├── web/                          the playable page (no framework, no Twine)
├── tests/                        offline tests for the engine and the cases
└── docs/                         architecture notes and deployment
```

## Run a case

```bash
cd storyteller
cp .env.local.example .env.local     # then set DEEPSEEK_API_KEY
python backend/server.py --case fox-and-crow
python backend/server.py --case cinderella
```

`--case` takes a directory name under `cases/` or a path to a case directory;
`STORYTELLER_CASE` is the fallback. One process plays one case. Python 3.13 and
the standard library only.

## Test

```bash
cd storyteller
python -m unittest discover -s tests -t .
```

The tests use a stub model: they never call the API and never spend credit.

## The loop, which every case shares

A story is a loop, and it ends only when the loop is broken. Walking the original
story to its usual end leads back to the first morning; only a break ends it, and
what counts as a break is the storyteller's judgement, guided by that case's canon.
Nothing in the engine scores it, and the page never tells the player the condition.

## What a case gives the agent

| File | Content |
| --- | --- |
| `case.json` | Story id, bilingual title, and the character the player plays |
| `world.en.md`, `world.zh.md` | The canon: cast, places, rules, prohibitions, and where the story can go |
| `opening.en.md`, `opening.zh.md` | The first passage the player reads |

That is the whole contract. There are no meters, clocks, or ending thresholds: the
storyteller decides what each turn changes, and the runtime only remembers the
turns and the facts it declares.

## Language

A session is played in one language (`en` or `zh`). The opening, every narration,
the hints, and the storyteller's own working notes are all written in that
language, and the model is given the canon written in it too. Switching language
in the page restarts the story in the other language.

## Read next

- `ARCHITECTURE.md` — how a turn flows, and what the runtime actually does.
- `docs/storyteller-skill.md` — the agent's role and how to change it.
- `../cases/<case>/README.md` — each story and what it is for.

For a hosted test, deploy the service described by `../render.yaml`: its root
directory is `storyteller/`, it runs `python backend/server.py`, and it serves the
page and the API from that one process.

Passing tests describe implementation behaviour only; they do not establish
narrative quality, Agent capability, author utility, or research validity.
