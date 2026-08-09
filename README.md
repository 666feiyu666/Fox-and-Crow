# The Fox and the Crow: A Day in Loop

This is a Twine adaptation of *The Fox and the Crow*. It implements the original fable as a fixed path, returns the player to the same morning when the day ends, and lets the player ask DeepSeek to narrate alternative actions.

The current version is deliberately small:

- You play a fox who has not eaten for three days.
- Each scene keeps one fixed choice from the original fable.
- Getting the cheese does not end the game; the day resets while the loop counter and the fox's memory persist.
- A free-text action can receive an immediate AI-narrated consequence without changing the fixed path.
- Turning successful free-text actions into permanent Twine choices is not included yet.

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
tests/test_server.py  Exercises the local API without calling DeepSeek
dist/index.html      Playable build output
```

## Current boundary

DeepSeek currently narrates an immediate response only. It does not navigate to another passage, change loop state, or save an action as a reusable choice. That promotion mechanism is the next development stage.
