# Storyteller

A reusable engine for playable stories in which a generative LLM agent acts as
Storyteller: an omniscient dungeon master that judges what each thing the player
says or attempts changes in the world, then narrates the consequence. There is no
branching script and no build step.

The engine holds no story of its own. Each playable story is a **case** under
`../cases/`, supplying canon, an opening, and the mechanics the runtime keeps.

```text
storyteller/
├── skills/storyteller/SKILL.md   the agent: role, procedure, output contracts
├── backend/                      case loader, state machine, two-phase agent, HTTP
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
`STORYTELLER_CASE` is the fallback. One process plays one case, so a deployment is
one story. Python 3.13 and the standard library only.

## Test

```bash
cd storyteller
python -m unittest discover -s tests -t .
```

The tests use a stub model: they never call the API and never spend credit.

## What a case provides

| File | Content |
| --- | --- |
| `case.json` | Case record plus a `storyteller` block: bilingual title, player character, meters, optional clock, ending floor |
| `world.md` | Canon given to the model: cast, places, objects, rules, prohibitions, mechanics |
| `openings.json` | The first passage, in English and Chinese |

No `clock` means the story spends no day units and never resets; the page then
shows turns instead of a day clock. Existing cases: `fox-and-crow` (a repeating
day) and `cinderella` (a single night, no loop).

## Read next

- `ARCHITECTURE.md` — how a turn flows, and which rules live in code.
- `docs/storyteller-skill.md` — the agent's role and how to change it.
- `docs/render-test-deployment.md` — a hosted test deployment.
- `../cases/<case>/README.md` — what each case is testing.

Passing tests describe implementation behaviour only; they do not establish
narrative quality, Agent capability, author utility, or research validity.
