# Render test deployment

`render.yaml` at the repository root describes a single Python web service whose
root directory is `storyteller/`. That one process serves both the playable page
and the Storyteller API for one case, so there is no front-end build and nothing
to upload separately.

## Deploy

1. Push this repository to the Git provider connected to Render.
2. Create a new Blueprint and select the repository. Render reads `render.yaml`.
3. When prompted, enter `DEEPSEEK_API_KEY`. Never commit the key.
4. Optionally set `STORYTELLER_CASE` to another case directory name. It defaults
   to `fox-and-crow`.
5. Wait for the deploy, then open the service URL.

`render.yaml` runs:

```text
buildCommand: python -m compileall backend
startCommand: python backend/server.py
healthCheckPath: /health
```

`--case` takes a directory name under `cases/` or an explicit path; the
`STORYTELLER_CASE` environment variable is the fallback, which is why the start
command needs no argument. Render supplies `RENDER` and `PORT`, so the server
binds to `0.0.0.0:$PORT` there and stays on `127.0.0.1:8000` locally.

## Verify a deployment

```text
https://YOUR-SERVICE.onrender.com/health           -> {"status":"ok","case":"..."}
https://YOUR-SERVICE.onrender.com/                 -> the playable page
```

Then play one turn. A working turn returns a narration, two or three suggested
actions, and an advanced clock or turn counter. A `503` means the key is missing
or has no balance; a `502` means the model returned a ruling the runtime rejected,
and the server terminal holds the detail.

## Expected test limitations

- The free service sleeps after inactivity; the first turn after a sleep is slower.
- Sessions are process-local. A restart or sleep clears them, and the player must
  restart the story.
- One deployment plays one case; serve another case as a second service.
- CORS stays open so a separately hosted copy of `web/` can reach the API during
  testing. Narrow it before any public release that adds authentication.
