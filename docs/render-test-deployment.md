# Render test deployment

This is the minimal deployment path for the friends-only itch.io test. It keeps
the existing standard-library HTTP server and process-local sessions.

## Deploy the backend

1. Push this repository to the Git provider connected to Render.
2. In Render, create a new Blueprint and select this repository. Render reads
   `render.yaml` from the repository root.
3. When prompted, enter `DEEPSEEK_API_KEY`. Do not add the key to the repository.
4. Wait for the deploy to finish, then open the service health endpoint:

   ```text
   https://YOUR-SERVICE.onrender.com/health
   ```

   It should return `{"status": "ok"}`.

Render supplies `RENDER` and `PORT`; `backend/server.py` therefore binds to
`0.0.0.0:$PORT` on Render while retaining `127.0.0.1:8000` for local use.

## Connect the itch.io build

1. Copy the service origin, without a trailing slash, for example:

   ```text
   https://fox-and-crow-story-api.onrender.com
   ```

2. Set `storyApiBaseUrl` near the beginning of `:: StoryScript` in
   `src/story.twee` to that origin.
3. Rebuild the story:

   ```powershell
   & '.\.tools\tweego-2.1.1\tweego.exe' -f sugarcube-2 -o '.\dist\index.html' '.\src'
   ```

4. Replace the existing itch.io upload with `dist/index.html` and test the
   dynamic story flow.

## Expected test limitations

- The free service sleeps after inactivity, so the first dynamic action can be
  slower while it starts.
- Sessions are stored in process memory. A Render restart or sleep clears them,
  and the player must restart the story.
- CORS intentionally allows browser requests from any origin for this test.
  Narrow it before a public release if authentication or cookies are added.
