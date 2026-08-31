# Repository guidance

This repository owns the Fox-and-Crow downstream narrative-AI task, its
formative Agent implementation, and the runnable MVP that will eventually
embody the revised solution.

- `agent/theory-guided-story-generator/` contains the imported Agent-building
  implementation and its independent Python environment and tests.
- `cases/fox-and-crow/` contains stable task inputs and author-reviewed briefs.
- The existing `backend/`, `src/`, and `dist/` paths are the current runnable
  MVP. They are not evidence that the Agent solution is complete or validated.
- Keep the Agent package separate from the MVP runtime until a specific rewrite
  step deliberately integrates them.
- Keep `.env.local`, virtual environments, local tools, media, presentation
  material, generated runs, and credentials out of Git.
- Read the relevant README, configuration, and tests before changing either the
  Agent implementation or the MVP.
- Passing software tests establishes implementation behavior only; it does not
  establish narrative quality, Agent capability, author utility, or research
  validity.
