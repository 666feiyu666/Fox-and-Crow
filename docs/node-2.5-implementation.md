# Node 2.5 Story-first implementation

## Frozen product defaults

- Six fixed time units per loop.
- Every successful Story Agent response consumes one unit.
- The sixth successful response unconditionally starts the next loop.
- First-person limited, present-tense narration.
- Five most recent visible turns as model context.
- Direct Story-first experience as the primary welcome action; the full fixed
  prologue remains available as a secondary entry.
- Existing Render + itch.io locations remain the intended distribution route, but
  deployment is not implied by local development.

## Turn contract

`POST /api/turn` accepts exactly:

```json
{
  "sessionId": "...",
  "inputType": "say",
  "content": "Tell me why you keep looking toward the bushes."
}
```

`inputType` must be `say` or `do`; empty or unknown input is rejected before the
model is called. SAY is exact player dialogue. DO is one attempted main action. The
Story Agent is instructed not to append player dialogue, promises, goals, decisions,
or additional major actions.

The server returns a typed `storyEntry`, the deterministic outcome, and the new
loop/time view. A failed model or network request never commits the candidate time or
visible-history state.

## Frontend behavior

- Welcome page with direct and full-prologue entries.
- SAY / DO segmented controls with mode-specific placeholders.
- Loop, phase, elapsed/remaining time, and Node 2.5 version label.
- Cold-start and generation feedback.
- Failed input remains in the textarea and can be retried.
- Story Log labels entries as `YOU SAID` or `YOU DID`.
- Restart discards the server session when reachable and always resets the browser.
- Responsive layout includes a compact mobile header and stacked time cards.

## Verification

- Baseline before implementation: 56 tests passed at `142fd35`.
- Node 2.5 unit/API/source regression suite covers the typed contract, one Story
  Agent call, deterministic time, loop rollover, five-turn context, failure
  non-commit, Story Log labels, restart, CORS, and responsive source structure.
- Twine compiles with Tweego 2.1.1 to `dist/index.html`.
- Local browser verification covers the welcome path, SAY / DO selection, dynamic
  placeholder, visible time, error feedback, retained retry input, and mobile layout.
- A live model response and hosted deployment remain environment-dependent checks.
