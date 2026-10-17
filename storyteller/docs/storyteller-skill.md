# The Storyteller skill

`storyteller/skills/storyteller/SKILL.md` is the agent: one file, loaded at
startup and sent with every request. It describes a storyteller who is
story-independent — someone who holds the whole world in view and answers the
player's line by showing what it changes.

The world is not in the skill. It arrives from the case, in `world.<lang>.md`, on
the same request, written in the session's language. That split is what lets one
agent tell many stories.

## The role

The storyteller knows what the case's canon says about everyone's goals, secrets,
and limits. The player knows only what one character has seen and been told, and
can do only one thing per turn. That asymmetry is the design: the player proposes,
the storyteller answers.

## Why two phases

A single model call tends to let the writing decide the outcome: the passage
sounds good, so the action succeeds. Separating the calls keeps judgement explicit:

1. **Ruling** — the storyteller answers in small JSON: `outcome`
   (`success`, `partial`, `failure`, `blocked`), a private `scene` plan, and any
   facts the turn fixes. None of it reaches the player.
2. **Narration** — a second call receives the ruling marked final and writes two to
   five sentences, plus two or three optional next actions.

The runtime validates the ruling before any prose exists, so a malformed or absurd
judgement is rejected instead of being written into the story.

## What the skill asks for

- Judge the aim, not the wording.
- Decide whether the world even allows the attempt, and say so through
  consequence rather than refusal.
- Failure always produces information, a cost, or a changed situation.
- Never speak for the player's character beyond what they wrote.
- Never invent named characters, powers, or rules the canon does not support.
- Keep the other characters' own goals intact; they are not devices.

There are no meters, scores, clocks, or ending conditions. The skill tells the
storyteller when a story has probably run its course, but the decision is theirs,
and nothing in the runtime overrides it.

## Language

Everything the model writes — `scene`, `facts`, `narration`, `hints` — is written
in `state.language` (`en` or `zh`), and the canon it is given is the same
language's version. A session never mixes languages.

## Changing a story or the engine

- To change how any story is told, edit `storyteller/skills/storyteller/SKILL.md`.
- To change one story, edit its case directory: `world.<lang>.md` for canon,
  `opening.<lang>.md` for the first passage, `case.json` for the title and the
  player's character. Both languages must be present.
- To add a story, copy a case directory, rewrite those files, and run
  `python backend/server.py --case <name>`.
- To change what the runtime guarantees, edit `backend/session.py` and its tests.

None of the data changes require touching Python; the server re-reads the case
when it starts.
