# Render test deployment

`render.yaml` at the repository root describes a single Python web service whose
root directory is `app/fox-and-crow-mvp/`. That one process serves both the
playable page and the Storyteller API, so there is no front-end build and nothing
to upload separately.

## Deploy

1. Push this repository to the Git provider connected to Render.
2. Create a new Blueprint and select the repository. Render reads `render.yaml`.
3. When prompted, enter `DEEPSEEK_API_KEY`. Never commit the key.
4. Wait for the deploy, then open the service URL. The page loads immediately; the
   first submitted line calls the Storyteller.

`render.yaml` runs:

```text
buildCommand: python -m compileall backend
startCommand: python backend/server.py
healthCheckPath: /health
```

Render supplies `RENDER` and `PORT`, so the server binds to `0.0.0.0:$PORT` there
and stays on `127.0.0.1:8000` locally.

## Verify a deployment

```text
https://YOUR-SERVICE.onrender.com/health           -> {"status":"ok"}
https://YOUR-SERVICE.onrender.com/                 -> the playable page
```

Then play one turn. A working turn returns a narration, two or three suggested
actions, and an advanced day counter. A `503` means the key is missing or has no
balance; a `502` means the model returned a ruling the runtime rejected, and the
server terminal holds the detail.

## Expected test limitations

- The free service sleeps after inactivity; the first turn after a sleep is slower.
- Sessions are process-local. A restart or sleep clears them, and the player must
  restart the story.
- CORS stays open so a separately hosted copy of `web/` can reach the API during
  testing. Narrow it before any public release that adds authentication.
