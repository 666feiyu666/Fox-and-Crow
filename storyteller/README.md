# Storyteller

A small engine for playable stories told by three LLM agents. A case ships only the
original tale.

1. **understand** reads that tale once per language and derives the case from it —
   the player's role, the world canon, and the opening passage — cached beside the
   case so it can be read, reviewed, and edited.
2. **judge** decides what the player's line changes in that world.
3. **write** turns that ruling into the passage the player reads.

They run as LangGraph state machines: one graph for understanding, one for the
turn. There is no branching script and no rulebook the engine enforces on top of
the world the tale implies.

```text
storyteller/
├── skills/understand/SKILL.md  the understander: reads the tale, derives the case
├── skills/judge/SKILL.md       the judge: weighs the action, returns the ruling
├── skills/writer/SKILL.md      the writer: turns the ruling into visible prose
├── backend/graph.py            the graphs (LangGraph): understand, judge -> write
├── backend/understanding.py    the derived case and its on-disk cache
├── backend/                    case loading, story state, model client, HTTP
├── web/                        the playable page (no framework, no Twine)
├── tests/                      offline tests for the graphs, the agents, the cases
└── docs/                       architecture notes
```

## Run a case

```bash
cd storyteller
python -m venv .venv                # or: uv venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt     # LangGraph
cp .env.local.example .env.local    # then set DEEPSEEK_API_KEY
python backend/server.py --case fox-and-crow
python backend/server.py --case cinderella
```

The first session in a language makes one extra model call: the understander reads
the tale and writes `cases/<case>/.generated/understanding.<lang>.json`. Later
sessions reuse it. Delete that file — or edit the tale — to have it derived again.

`--case` takes a directory name under `cases/` or a path to a case directory;
`STORYTELLER_CASE` is the fallback. One process plays one case.

## Test

```bash
cd storyteller
python -m unittest discover -s tests -t .
```

The tests use a stub model: they never call the API and never spend credit.

## The loop, which every case shares

A story is a loop, and it ends only when the loop is broken. Walking the original
story to its usual end leads back to the first morning; only a break ends it, and
what counts as a break is the judge's decision, guided by the derived canon.
Nothing in the engine scores it, and the page never tells the player the condition.

## What a case gives the agent

| File | Content |
| --- | --- |
| `case.json` | Story id and bilingual title |
| `source.en.md`, `source.zh.md` | The original tale, which is all the agents read |

Everything else — the player's role, the canon, the opening passage — is derived
from the tale on first use and cached under `cases/<case>/.generated/`. That cache
is plain JSON: read it, edit it, or delete it to force a fresh reading.

## Language

A session is played in one language (`en` or `zh`). The tale is read and the case
derived in that language, so the opening, every narration, the hints, and the
judge's own notes are all in it. Switching language in the page restarts the story
in the other language, reusing that language's derivation.

## Read next

- `ARCHITECTURE.md` — how a turn flows, and what the runtime actually does.
- `docs/agent-skills.md` — the three agents and how to change them.
- `../cases/<case>/README.md` — each story and what it is for.

For a hosted test, deploy the service described by `../render.yaml`: its root
directory is `storyteller/`, it runs `python backend/server.py`, and it serves the
page and the API from that one process.

Passing tests describe implementation behaviour only; they do not establish
narrative quality, Agent capability, author utility, or research validity.
