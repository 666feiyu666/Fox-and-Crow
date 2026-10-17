# The Fox and the Crow

The first Track B1 case for studying counterfactual alternative action
generation and consequence projection. It is not a generic input contract for
all story-level narrative techniques.

The bounded question is: what could the fox do if it does not use deception to
obtain the cheese, and what might those alternatives change about subsequent
events, endings, theme, and educational meaning?

`case.json` records the confirmed problem boundary. It deliberately does not
list candidate strategies or expected meanings, because those would leak
answers into an evaluation of the Agent's ability to imagine alternatives.

## As a Storyteller case

The `storyteller` block of `case.json` makes this case playable by the engine in
`../../storyteller/`:

| File | Role |
| --- | --- |
| `case.json` → `storyteller` | Bilingual title, player character (`the fox` / `狐狸`), a six-unit day clock that loops, meters `trust` and `insight`, and an ending floor of eight turns with both meters at 3 |
| `world.md` | Canon given to the model: cast, places, rules, prohibitions, and the meaning of each meter |
| `openings.json` | The first passage, in English and Chinese |

Run it with:

```bash
cd storyteller
python backend/server.py --case fox-and-crow
```

This case gives the agent a machine — a repeating day, a price for every action,
trust that resets each morning. That machinery is what the Cinderella case
removes, so the two are useful together: one tests judgement inside a mechanism,
the other without one.

This case is a test input for the agent, not evidence that a particular Agent
solution has been validated.
