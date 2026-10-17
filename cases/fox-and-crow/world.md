# World canon — The Fox and the Crow: A Day in Loop

This file is the story bible the Storyteller must obey. It is adapted from the
repository's reviewed Fox-and-Crow world configuration. It is canon: nothing in
a ruling may contradict it, and nothing may be added to it mid-story.

## Premise

Aesop's fable, turned into a looping day. A fox wakes hungry beneath the tree
where a crow holds cheese in her beak. The fox wants the cheese, then wants out
of the forest, then wants to understand why the day keeps returning. The bridge
out of the forest is broken. The crow has lost something in the thorns. Only the
fox remembers the previous loops.

## Cast

### The fox (the player)

- Sharp-eyed, quick to read a situation, used to winning by flattery and
  calculation; proud, and unwilling to admit helplessness.
- Wants, in order: the cheese; a way out of the forest; an explanation for the
  loop.
- Believes at first that the right words make anyone move as intended, and that
  the loop must have one switch to find by trial and error.
- Knows the forest, the river, and the road to the bridge — but not that the
  bridge is down. Does not know the crow is searching for a necklace. Does not
  know, at first, that it is in a loop.
- May only act on what it has seen, heard, remembered, or inferred.
- Keeps memory, learned methods, and emotional weight across resets. Its body
  resets.
- Must change its judgement after failure; repeating a proven failure unchanged
  is a choice with consequences, not a free retry.

### The crow

- Wary, practical, and not stupid. She distrusts eager, unexplained approaches.
- Wants: her necklace back from the thorn bush; to keep her cheese; to leave the
  forest once the necklace is found. If she comes to trust the fox, she can fly
  beyond the river and bring people who can repair the bridge.
- Believes actions over words. Needs verifiable evidence before revising her
  judgement — but does revise it when evidence arrives.
- Knows the necklace fell near the thorns and that her wings cannot safely reach
  into them. Knows she can cross the river by air. Does not know the fox keeps
  its memory from day to day.
- Keeps no explicit memory across resets. Repeated sincere contact may leave a
  faint, unexplained familiarity, but that never lets her skip verification in
  the current day.
- Is never merely a clue dispenser or a comfort for the fox. She has her own
  goals and can refuse, ask, leave, or surprise.

## Places

- **Forest** — the whole story space, ringed by a wide, fast river. Contains the
  mossy clearing where the fox wakes, the old tree where the crow perches, and
  the thorn bush. Each loop begins at the same misty, damp morning.
- **River** — too deep and fast for a fox. The broken bridge is the only land
  route out.
- **Old tree** — the crow's perch, holding the cheese. The fox cannot climb to
  that branch.
- **Thorn bush** — dense, close to the ground, in sight of the tree. The necklace
  is caught between its spines; a fox can part the branches from below.

## Objects and obstacles

- **Cheese** — in the crow's beak at the start of every day. Can be tricked away,
  shared, or left. It never ends the loop.
- **Necklace** — a small chain caught deep in the thorn bush, glinting at certain
  angles of the morning light. Returns to the thorns on every reset, even if it
  was returned. Returning it changes how the fox understands the crow, but does
  not by itself end the loop.
- **Broken bridge** — the only land route out, washed out before the story
  begins. Too wide to jump, too weak to patch by one fox; any repair the fox
  makes alone vanishes at reset.

## Facts fixed before play

- The necklace is already in the thorn bush; the crow cannot safely reach it.
- The bridge is already broken; the fox does not know this yet.
- People who could repair the bridge exist beyond the river, but nothing
  unfinished survives a reset.
- The fox and the crow are not friends when the story begins.

## Rules of the world

- The fox is inside a time loop anchored to the same morning. The day returns
  when night falls or the fox dies or loses consciousness.
- The fox is the only character who keeps explicit memory. Everything else
  resets: time, weather, light, object positions, the bridge, the crow's body
  and explicit memory.
- The crow does not remember the previous loop. A reset restores her wariness;
  trust must be earned again within the day.
- No single act — cheese, necklace, death, or leaving the forest — ends the loop.
- The loop ends only when the fox stops treating the crow as a tool or as the
  key to escape, tells the truth about the loop without asking for anything in
  return, and the crow, on verifiable grounds, chooses to trust and respond.
  Neither character can know this rule directly.
- After the loop ends, time runs forward normally, and both characters keep the
  memory, relationship, and physical situation they had formed in the last day.

## Prohibitions

- Do not enter the crow's, or anyone's, interior. Her mind is shown only through
  conduct, distance, timing, and speech.
- Do not let the fox's guesses become objective fact in narration.
- Do not resolve the central problem with a lucky clue, a sudden power, or a
  stranger's explanation. Key discoveries come from observable action.
- Do not add named characters, factions, lore, conspiracies, or new loop rules.
  The bridge-repairers remain anonymous and offstage until the ending.
- Do not portray the friendship as sudden, romantic, or won by one moving
  speech. It is built through repeated contact, risk, misunderstanding, and
  response.
- Do not render injury, drowning, or despair as spectacle, and never as comedy.
- Do not use fable-style moralizing, meta-commentary, or a closing explanation
  of the theme.

## Mechanics declared for this case

These are the numbers the runtime keeps and the Storyteller may move.

- **Clock.** A day holds six units. Every ruling prices the action in units (0–3)
  by how much of the day it consumes. When the six units are spent, night falls
  and the loop begins the same morning again.
- **Meter `trust`** (range −3 to 6, starts at 0). How far the crow trusts the fox.
  It rises with verifiable, non-manipulative action and falls with flattery,
  pressure, taking, or being caught in a lie.
- **Meter `insight`** (range 0 to 6, starts at 0). How much the fox understands
  the loop and the crow's situation. It rises only from observation, evidence, or
  a failure that teaches something.
- **Reset.** A new morning returns `trust` to 0 because the crow keeps no memory;
  `insight` and the established facts stay with the fox.
- **Ending.** Set `ending` to `end` only when the fox has stopped treating the
  crow as a tool or as the key to escape, has told the truth about the loop
  without asking for anything in return, and the crow — on verifiable grounds —
  has chosen to trust and respond. Cheese, the necklace, death, and leaving the
  forest alone never end it.
