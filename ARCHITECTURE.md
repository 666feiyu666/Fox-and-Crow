# Runtime architecture

This document describes the current code boundaries after the responsibility-based
refactor. The refactor preserves the existing player flow; it does not implement new
Game Agent, Story Agent, or game-system behavior.

## Core responsibilities

```text
Player input
    -> Game Agent interprets the attempted action
    -> Game system validates and applies authoritative rules
    -> Story Agent narrates confirmed public events
    -> Application layer commits the candidate state
```

- The **game system** owns authoritative state, deterministic transitions, character
  knowledge projections, public events, and ending rules.
- The **Game Agent** interprets natural-language input. Its output is a proposal and
  cannot directly mutate authoritative state.
- The **Story Agent** turns player-visible context and confirmed events into prose. Its
  narration does not become authoritative state by itself.
- The **application layer** coordinates a transactional turn without owning prompts or
  story-specific rules.

## Package map

| Package | Responsibility |
|---|---|
| `backend/game_system/` | Authoritative state and deterministic Fox-and-Crow rules |
| `backend/game_agent/` | Game Agent port and the existing bounded-effect experiment |
| `backend/story_agent/` | Story Agent and narrative-grounding ports |
| `backend/application/` | Turn coordination and commit ordering |
| `backend/infrastructure/` | DeepSeek and in-memory session-store adapters |
| `backend/server.py` | HTTP validation, response mapping, and static-file serving |

The historical development-node numbers are intentionally absent from runtime module
names. `fox_crow.py` names the scenario whose current rules it contains; it is not
presented as a general game engine.

## Turn boundary

`TurnCoordinator` depends on the Game Agent, Story Agent, narrative grounder, session
store, and game-system functions through their responsibilities. The current local
runtime supplies one `DeepSeekAgentGateway` instance for all model-backed ports, but
the ports are separate so each capability can be developed and evaluated independently
without changing the game rules or the coordinator.

State is committed only after action interpretation, deterministic resolution,
narration, and grounding have succeeded. When narration fails grounding twice, the
existing confirmed-public-event fallback remains in place.

## Current limits

- The current scenario still contains only the existing necklace path.
- The generic effect proposal parser remains an isolated experiment and is not wired
  into the playable turn.
- Sessions remain process-local and disappear when the server restarts.
- The DeepSeek adapter currently implements all Agent ports; separating models or
  prompts further is future capability work, not part of this refactor.
