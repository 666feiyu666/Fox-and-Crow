# Storyteller

A small engine for playable stories told by four LLM skills. A case ships only the
original tale.

1. **understand** comes first. It reads that tale, makes semantic sense of it, and
   abstracts it into canon and a structured story space — the player's role, the
   world, the situation and its initial facts, uncommitted possibilities, the
   loop's authored convention, and the writing voice — cached beside the case so it
   can be reviewed and edited. Everything the later skills do is grounded in it.
2. **judge** decides what the player's line changes in that world.
3. **write** turns that ruling into the passage the player reads, and renders the
   opening the preparation hands over.
4. **review** is a content editor: it checks direction, coherence and voice before
   a passage is published, and can send one bounded repair back to the judge or the
   writer.

They run as LangGraph state machines: one graph prepares a case
(`understand -> write_opening`), one runs a turn (`judge -> write -> review`), with
conditional edges back for a repair. There is no branching script and no rulebook
the engine enforces on top of the world the tale implies.

```text
storyteller/
├── skills/understand/SKILL.md     the understander: reads the tale, derives the case
├── skills/judge/SKILL.md          the judge: weighs the action, returns the ruling
├── skills/writer/SKILL.md         the writer: turns the ruling into visible prose
├── skills/reader-review/SKILL.md  the editor: reviews a passage before publication
├── backend/graph.py               the graphs (LangGraph): preparation, turn, repair
├── backend/understanding.py       the derived story space and its on-disk cache
├── backend/                       case loading, story state, model client, HTTP
├── web/                           the shelf and the playable page (no framework)
├── tests/                         offline tests for the graphs, the skills, the cases
└── docs/                          architecture notes
```

## Run a case

```bash
cd storyteller
python -m venv .venv                # or: uv venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt     # LangGraph
cp .env.local.example .env.local    # then set DEEPSEEK_API_KEY
python backend/server.py                        # every case on the shelf
python backend/server.py --case fox-and-crow    # or just one
```

The first session in a language runs the preparation calls: the understander reads
the tale and the writer renders the opening, and the result is written to
`cases/<case>/.generated/understanding.<lang>.json`. Later sessions reuse it.
Delete that file — or edit the tale — to have it derived again.

`--case` takes a directory name under `cases/` or a path to a case directory;
`STORYTELLER_CASE` is the fallback. Without either, one process serves every case
under `cases/`, the page opens on the shelf, and each case gets its own
Storyteller.

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

The server serves the page and the API from one process on `127.0.0.1:8000` by
default; `--host` and `--port` override that.

Passing tests describe implementation behaviour only; they do not establish
narrative quality, Agent capability, author utility, or research validity.
