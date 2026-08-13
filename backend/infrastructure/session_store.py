from __future__ import annotations

from dataclasses import replace
from threading import RLock
from uuid import uuid4

from backend.game_system.state import GameState, initial_game_state
from backend.story_runtime.state import StorySessionState, initial_story_state


class SessionStoreError(ValueError):
    pass


class SessionNotFoundError(SessionStoreError):
    pass


class StaleSessionError(SessionStoreError):
    pass


class InMemoryGameSessionStore:
    """Process-local optimistic store for authoritative game state."""

    def __init__(self) -> None:
        self._states: dict[str, GameState] = {}
        self._lock = RLock()

    def create(self, loop_count: int = 3) -> tuple[str, GameState]:
        state = initial_game_state()
        state = replace(state, loop=replace(state.loop, loop_count=loop_count))
        session_id = uuid4().hex
        with self._lock:
            self._states[session_id] = state
        return session_id, state

    def get(self, session_id: str) -> GameState:
        with self._lock:
            try:
                return self._states[session_id]
            except KeyError as error:
                raise SessionNotFoundError("Unknown or expired story session.") from error

    def commit(self, session_id: str, expected: GameState, updated: GameState) -> None:
        with self._lock:
            current = self._states.get(session_id)
            if current is None:
                raise SessionNotFoundError("Unknown or expired story session.")
            if current != expected:
                raise StaleSessionError(
                    "The story changed while this action was being resolved."
                )
            self._states[session_id] = updated

    def discard(self, session_id: str) -> None:
        """Forget a session without revealing whether it previously existed."""
        with self._lock:
            self._states.pop(session_id, None)


class InMemoryStorySessionStore:
    """Process-local optimistic store for the Node 2.5 Story-first runtime."""

    def __init__(self) -> None:
        self._states: dict[str, StorySessionState] = {}
        self._lock = RLock()

    def create(self, loop_count: int = 1) -> tuple[str, StorySessionState]:
        state = initial_story_state(loop_count=loop_count)
        session_id = uuid4().hex
        with self._lock:
            self._states[session_id] = state
        return session_id, state

    def get(self, session_id: str) -> StorySessionState:
        with self._lock:
            try:
                return self._states[session_id]
            except KeyError as error:
                raise SessionNotFoundError("Unknown or expired story session.") from error

    def commit(
        self,
        session_id: str,
        expected: StorySessionState,
        updated: StorySessionState,
    ) -> None:
        with self._lock:
            current = self._states.get(session_id)
            if current is None:
                raise SessionNotFoundError("Unknown or expired story session.")
            if current != expected:
                raise StaleSessionError(
                    "The story changed while this turn was being generated."
                )
            self._states[session_id] = updated

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._states.pop(session_id, None)
