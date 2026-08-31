# The Fox and the Crow: A Day in Loop

You play as the fox from Aesop's fable *The Fox and the Crow*. At first, you follow the story exactly as it has always been told: flatter the crow, persuade her to sing, and seize the cheese when it falls from her beak.

But victory does not set you free. The next morning, you wake beneath the same tree, facing the same crow and the same piece of cheese. As the fable repeats, small details begin to feel wrong—and the crow's anxious glances toward the bushes suggest that her story has never really been about the cheese.

To escape the loop, you must stop playing the role the fable wrote for you. What will you say or do when the old trick is no longer enough, and how can the fox create an ending that the original story never imagined?

## Repository roles

Fox-and-Crow is the downstream task for a theory-guided Narrative AI solution.
The existing `backend/`, `src/`, and `dist/` implementation is the current
runnable MVP and will be rewritten as that solution is refined.

The prior Agent-building implementation now lives under
`agent/theory-guided-story-generator/`. It captures an existing approach based
on explicit plot structure, story-world constraints, recursive generation
context, and human acceptance of each generated section. It is a starting point
for the rewrite, not a validated final Agent.

Stable Fox-and-Crow task inputs live under `cases/fox-and-crow/`.
