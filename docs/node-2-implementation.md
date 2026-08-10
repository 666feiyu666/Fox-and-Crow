# Node 2 implementation and verification

Status: implemented and locally verified on 2026-08-10; live fallback path still needs browser revalidation

## Delivered player flow

Node 2 completes one vertical story slice:

1. The player repeats the authored fable for three days.
2. Each repetition adds stronger signs that the crow has concerns beyond the cheese.
3. Day 4 replaces the fixed affordance with a natural-language action box.
4. The player asks what is wrong, searches the bushes, and returns the lost necklace.
5. The crow reciprocates, the friendship rules become true, and the day ends without rewinding.

The player does not need to enter exact sentences. DeepSeek classifies the semantic intent of each action.

## Runtime boundaries

| Component | Responsibility |
|---|---|
| Twine / SugarCube | First three authored loops, Day 4 interface, player input, result passages, and fox-known memories |
| `/api/session` | Starts an in-memory authoritative Node 2 session at Day 4 |
| DM Agent | Classifies the action as asking, searching, returning, or another action and proposes a bounded time cost |
| Python state rules | Apply only permitted necklace, character, relationship, time, hunger, and memory transitions, then emit typed public events |
| Narrative context | Derives only the visible scene, the fox's condition, and knowledge already held by the fox |
| Story Agent | Freely narrates the action and confirmed public events from the fox's perspective |
| Grounding Agent | Semantically checks every proposed story fact against the same public sources and requests one rewrite when unsupported |
| Public-event fallback | After two rejected narrations, assembles safe prose directly from Python-confirmed public-event descriptions |
| Session store | Commits grounded or deterministic-fallback turns and rejects stale concurrent updates |

The previous `/api/action` endpoint remains available for the Node 1 prototype. Node 2 uses `/api/session` and `/api/turn`.

## Player story log and restart

- A `Story Log` button is available from every passage without advancing the story.
- The log offers only days the player has visited and opens on the current day.
- Each fixed or free-text action is paired with the story that followed it.
- Only player-visible text is recorded; failed requests and hidden state never enter the log.
- Returning from the log preserves the current passage and any unfinished action input.
- `Restart the story` requires confirmation, cancels the active browser request, discards the backend session, clears Twine history and the journal, and returns to Day 1.
- Backend session cleanup is idempotent, so a repeated restart cannot reveal or depend on whether the old session still exists.

## Player information boundary

The backend owns the complete state, but the player does not see that representation. The browser receives only:

- the session identifier needed to continue the same play session;
- narration and the day outcome needed to choose the next passage;
- the loop count and memories already learned by the fox.

Trust and hunger numbers, object location and ownership, problem-revealed flags, relationship counters, classified intent, confirmed-fact lists, Agent names, and model configuration stay inside the backend. Errors shown during play use story-level language and do not identify the model, Agent role, or failed internal validation.

The three model responsibilities receive deliberately different inputs. The DM Agent receives the complete authoritative state so it can interpret actions and select a bounded intent and time cost. Python applies the transition and converts it into typed public events. The Story Agent receives only the before/after fox perspective, the player's words, and those events, while retaining freedom over pacing, atmosphere, and sensory expression. The Grounding Agent receives the same public sources plus the proposed narration, but never receives the hidden authoritative state.

This is an event-ownership and semantic-grounding boundary, not a post-generation word filter. For example, sleeping emits only `time_passes_hungrier`. Searching the bushes before learning the crow's problem emits `fox_searches_bushes` and `search_inconclusive`, but no necklace event. The Story Agent may freely describe those moments, but unsupported story facts cause a rewrite. Because both Story and Grounding roles are probabilistic calls to the same configured model, the audit can reject harmless prose. After two rejected narrations, the server therefore uses only the confirmed public-event descriptions as a deterministic fallback instead of failing the whole turn.

## Authoritative state

The resettable day state now includes:

- the crow's problem-revealed flag;
- a bushes location;
- the crow's lost necklace as a world item;
- necklace location and ownership;
- trust, supportive action, reciprocal action, time, hunger, and character locations.

Fox memories remain in loop state and survive a failed day. The necklace, crow state, and other day state reset.

## Golden-path rules

- Asking about the crow's distress reveals the necklace problem, records the clue, and raises trust by one.
- Searching succeeds only after the fox has learned the clue. It moves the fox to the bushes and transfers the necklace to the fox.
- Returning succeeds only while the fox owns the necklace. It returns the item, records support and reciprocity, raises trust to the friendship threshold, and consumes the remaining day.
- A completed friendship produces `loop_escaped`; an expired or starved day resets while retaining fox memories.
- Retryable DeepSeek transport failures (`429` and selected `5xx` responses, URL errors, and timeouts) receive up to three attempts; final failures and invalid DM responses do not commit the candidate state.
- Authentication, balance, rate-limit, request-format, and other provider failures are logged with their real upstream detail while the player receives a bounded actionable message.

## Implementation locations

| File | Role |
|---|---|
| `backend/game_system/state.py` | Necklace, bushes, crow problem state, existing friendship and reset rules |
| `backend/game_system/fox_crow.py` | Scenario intents, public events, deterministic transition rules, perspective context, and restricted player view |
| `backend/application/turns.py` | Transactional coordination across action interpretation, rules, narration, grounding, and commit |
| `backend/infrastructure/deepseek.py` | DeepSeek Game Agent, Story Agent, and Grounding adapters |
| `backend/infrastructure/session_store.py` | Process-local authoritative session storage |
| `backend/server.py` | Session, turn, reset, and compatibility HTTP endpoints |
| `src/story.twee` | Three authored loops, Day 4 action UI, player story log, full restart, dynamic result passage and final tomorrow |
| `tests/test_fox_crow_rules.py` | Golden path, prerequisite, reset, parser and stale-turn tests |
| `tests/test_server.py` | HTTP golden path, prompt-boundary, rewrite, and no-commit-on-DM-failure tests |

## Verification evidence

- All 53 Python tests pass, including the HTTP golden path, retry behavior, actionable balance errors, no-commit-on-DM-failure, rewrite-before-commit, and deterministic fallback after two grounding rejections.
- Tweego 2.1.1 builds `dist/index.html` successfully with SugarCube 2.30.0.
- The direct `backend/server.py` entry point loads successfully.
- An earlier real `deepseek-v4-flash` browser run classified and narrated all three golden-path actions; the current configuration uses `deepseek-v4-pro`.
- A minimal real `deepseek-v4-pro` JSON diagnostic succeeded with the current key, base URL, and model configuration.
- The browser reached Day 4 only after the three authored loops.
- Automated state tests verified trust `0 → 1 → 3`, necklace `lost → found → returned`, and time `6 → 5 → 3 → 0` without exposing those values in the browser.
- HTTP tests verify that player responses exclude the internal state, classified intent, confirmed facts, and model metadata.
- Automated coverage verifies the Story/Grounding prompt boundary, rewrite-before-commit behavior, and the public-event fallback. The latest fallback has not yet been exercised through a complete live browser golden path.
- Earlier browser regression verified day selection, fixed and generated action-to-story records, return to the current passage, confirmation cancellation, and full restart.
- The browser currently reports a non-fatal Permissions Policy warning for `unload`; this is separate from the story API and does not cause the observed `502` responses.
- A failed real API attempt preserved the player's input, and automated tests confirm that DM failure does not commit state.

## Current limits

- Sessions are held in memory and are lost when the local server restarts.
- Node 2 implements only the necklace setting and does not prove a second solution path.
- The DM intent vocabulary is intentionally limited to the current vertical slice.
- Grounding is semantic and probabilistic rather than an absolute guarantee. It can reject harmless literary detail because the Story and Grounding roles interpret the same evidence boundary differently.
- The deterministic fallback preserves availability and factual grounding at the cost of less expressive prose; this is a mitigation for the current architecture, not proof that the multi-Agent audit design is optimal.
- General character-object authoring, persistence, and deployment are outside Node 2.
