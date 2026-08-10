# The Fox and the Crow: A Day in Loop

This is a Twine adaptation of *The Fox and the Crow*. It implements the original fable as a fixed path, returns the player to the same morning when the day ends, and lets the player ask DeepSeek to narrate alternative actions.

The current version is deliberately small:

- You play a fox who has not eaten for three days.
- Each scene keeps one fixed choice from the original fable.
- Getting the cheese does not end the game; the day resets while the loop counter and the fox's memory persist.
- Every valid free-text action opens a generated Twine passage containing the player's action and its AI-narrated consequence.
- DeepSeek can promote a concrete action with a meaningful consequence or reusable information into a remembered choice for that scene, including useful partial successes and failures.
- Remembered choices persist through later loops in the current playthrough and replay their known result without another API request.

## Requirements

- Windows PowerShell 5.1 or later
- Python 3.10 or later
- An internet connection for the first Tweego download
- A modern web browser
- A DeepSeek API key for free-text actions

The project uses Tweego 2.1.1 and its bundled SugarCube 2.30.0 story format. Tweego is installed locally under `.tools/` and is not committed to Git.

## First run

Download the Windows x64 archive for [Tweego 2.1.1](https://github.com/tmedwards/tweego/releases/tag/v2.1.1), then extract it so the executable is located at:

```text
.tools\tweego-2.1.1\tweego.exe
```

Build the story from the project root:

```powershell
& '.\.tools\tweego-2.1.1\tweego.exe' -f sugarcube-2 -o '.\dist\index.html' '.\src'
```

The compiled file is committed, so the fixed story can also be opened directly from `dist/index.html`. Free-text actions require the local server below.

## Run with DeepSeek

Create a private local configuration file from the committed example:

```powershell
Copy-Item .env.local.example .env.local
notepad .env.local
```

Add your key after `DEEPSEEK_API_KEY=` in `.env.local`, then start the local server:

```powershell
python .\backend\server.py
```

Open `http://127.0.0.1:8000` in a browser. Stop the server with `Ctrl+C`.

If `python` is not available on `PATH`, replace it with the full path to a Python 3.10 or later executable.

The server automatically loads `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, and `DEEPSEEK_BASE_URL` from `.env.local`. Explicit process environment variables take priority over values in the file.

The server defaults to `deepseek-v4-flash`. To choose another currently supported model, edit `.env.local`:

```text
DEEPSEEK_MODEL=deepseek-v4-pro
```

The API key remains in the backend process and is never sent to the browser. Do not put it in the story source or commit it to Git.

## Documentation

- [Node 1 implementation](docs/node-1-implementation.md) — delivered player flow, component boundaries, evidence, and current limits
- [Development progress](docs/development-progress.md) — evidence-backed delivery status for Node 1 only
- [Notion documentation workflow](docs/notion-documentation-workflow.md) — reusable process and template for keeping Notion aligned with the repository

## Verify

```powershell
& '.\.tools\tweego-2.1.1\tweego.exe' -f sugarcube-2 -o '.\dist\index.html' '.\src'
python -m unittest discover -s tests -v
```

The first command validates and rebuilds the Twine story. The Python tests exercise the backend and DeepSeek request format with local stubs; they do not call DeepSeek or consume API credit.

## Project structure

```text
src/story.twee       Twine/Twee story source and styles
.env.local.example   Safe template for local DeepSeek configuration
backend/server.py     Serves the story and proxies validated actions to DeepSeek
backend/game_state.py Defines the authoritative day, character, world, and loop state rules
backend/action_resolution.py Parses and validates the restricted effects proposed by an AI resolver
tests/test_server.py  Exercises the local API without calling DeepSeek
tests/test_game_state.py Verifies time, friendship, starvation, ownership, and loop reset rules
tests/test_action_resolution.py Rejects unauthorized, inconsistent, and out-of-bounds AI proposals
dist/index.html      Playable build output
docs/node-1-implementation.md Consolidated Node 1 implementation and verification record
docs/development-progress.md Evidence-backed Node 1 delivery ledger
docs/notion-documentation-workflow.md Reusable Notion documentation process
```

## Current boundary

DeepSeek narrates an immediate response and decides whether the action produced a meaningful consequence or reusable information. Every valid response becomes a generated passage. Meaningful actions become remembered choices in SugarCube story state, keyed by passage and deduplicated by action text. They survive later time loops in the current playthrough but are not yet stored across a fresh browser session.

Remembered actions navigate to the generated `A New Turn` passage and replay their known immediate consequence without another API request. They do not alter the fixed story route or create a persistent branching graph.

The backend now has a tested, immutable game-state core that separates resettable day state from fox-only loop memory. It enforces positive time costs, bounded hunger, item ownership, formal friendship conditions, and end-of-day reset or escape. This core is not connected to `/api/action` or the Twine interface yet.

AI state-resolution proposals now have a strict, state-aware protocol. The validator accepts only named effects such as character movement, bounded hunger or trust changes, relationship events, food discovery, and item transfer or consumption. It rejects direct friendship or terminal decisions, unknown world references, duplicate item IDs, exhausted resources, and extra fields. Validated effects are not applied to game state yet. This README does not define the next node.
