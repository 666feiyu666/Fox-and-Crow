# Fox-and-Crow MVP

A playable story built on Aesop's fable. You are the fox; a Storyteller agent with
an omniscient view holds the world and judges what each line you say or action you
attempt changes. Nothing is scripted in advance: the Storyteller rules on your
input, then narrates the consequence, and the runtime keeps the day, the loop, and
the relationship honest.

```text
app/fox-and-crow-mvp/
├── skills/storyteller/   the agent: role, world canon, opening (sent on every turn)
├── backend/              session state, two-phase Storyteller, model client, HTTP
├── web/                  the playable page (no build step, no Twine)
├── tests/                offline tests for the rules, the agent, and the API
└── docs/                 architecture notes and deployment
```

## Run it

```bash
cd app/fox-and-crow-mvp
cp .env.local.example .env.local     # then set DEEPSEEK_API_KEY
python backend/server.py             # http://127.0.0.1:8000
```

Python 3.13 and the standard library only. The page is served by the same process;
there is nothing to build.

## Test it

```bash
cd app/fox-and-crow-mvp
python -m unittest discover -s tests -t .
```

The tests use a stub model, so they never call the API and never spend credit.

## Read next

- `ARCHITECTURE.md` — how a turn flows and what the runtime guarantees.
- `docs/storyteller-skill.md` — the agent's role, the two phases, how to change it.
- `docs/render-test-deployment.md` — a hosted test deployment.

Passing tests describe implementation behaviour only; they do not establish
narrative quality, Agent capability, author utility, or research validity.
