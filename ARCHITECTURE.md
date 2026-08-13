# Node 2.5 runtime architecture

Node 2.5 is the active, distributable Story-first prototype. It intentionally does
not implement the three-layer Node 3 architecture.

```text
SAY or DO input
    -> HTTP validation
    -> Story Agent (one model call)
    -> deterministic one-unit time advance
    -> optimistic session commit
    -> narration, time, and Story Log UI
```

## Active responsibilities

- `backend/server.py` validates `say` / `do`, maps errors, and exposes session APIs.
- `backend/application/turns.py` enforces the generate-then-commit transaction.
- `backend/story_runtime/state.py` owns only loop number, elapsed/remaining time,
  time phase, and the five most recent visible turns used as narrative context.
- `backend/story_agent/` defines the single Story Agent port.
- `backend/infrastructure/deepseek.py` implements that port with one model request.
- `src/story.twee` owns the welcome flow, input mode, visible time, loading/error
  feedback, Story Log, restart flow, and responsive presentation.

The Story Agent produces visible prose only. It does not decide victory, escape,
inventory, relationships, trust, hunger, or other authoritative state. Every usable
response costs exactly one of six time units. When the sixth unit is consumed, the
runtime unconditionally starts the next loop. Model or network failure leaves the
session unchanged.

## Historical Node 2 code

`backend/game_system/`, `backend/game_agent/`, and their focused tests remain as
historical comparison material tied to baseline commit `142fd35`. They are not
imported by the Node 2.5 server path and must not be mistaken for active runtime
state. Node 3 can replace this simplified runtime after its architecture is verified.

## Current limits

- Sessions are process-local and are lost when the server restarts.
- The five-turn context is visible-story memory, not structured world state.
- Free input cannot determine victory or escape from the loop in Node 2.5.
- Deployment and hosted mobile verification are separate from local completion.
