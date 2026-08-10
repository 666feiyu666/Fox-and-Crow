# The Fox and the Crow: A Day in Loop

You play as the fox from Aesop's fable *The Fox and the Crow*. At first, you follow the story exactly as it has always been told: flatter the crow, persuade her to sing, and seize the cheese when it falls from her beak.

But victory does not set you free. The next morning, you wake beneath the same tree, facing the same crow and the same piece of cheese. As the fable repeats, small details begin to feel wrong—and the crow's anxious glances toward the bushes suggest that her story has never really been about the cheese.

To escape the loop, you must stop playing the role the fable wrote for you. What will you say or do when the old trick is no longer enough, and how can the fox create an ending that the original story never imagined?

## Architecture

The backend is organized by long-term responsibility rather than development-node
numbers: authoritative game rules, Game Agent interpretation, Story Agent narration,
application coordination, and infrastructure adapters. See
[`ARCHITECTURE.md`](ARCHITECTURE.md).
