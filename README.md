# The Fox and the Crow: A Day in Loop

This is the first development stage of a Twine adaptation of *The Fox and the Crow*. It implements the original fable as a fixed path, then returns the player to the same morning when the day ends.

The current version is deliberately small:

- You play a fox who has not eaten for three days.
- Each scene offers one fixed choice from the original fable.
- Getting the cheese does not end the game; the day resets while the loop counter and the fox's memory persist.
- Free-text input, the DeepSeek API, and generated choices are not included yet.

## Requirements

- Windows PowerShell 5.1 or later
- An internet connection for the first Tweego download
- A modern web browser

The project pins Tweego 2.1.1 and uses its bundled SugarCube 2.30.0 story format. The tool is installed under `.tools/` and is not committed to Git.

## First run

From the project root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

Then open `dist/index.html` in a browser. The compiled file is committed, so the story can also be played without installing the build tools.

## Verify

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

The verification script rebuilds the story and checks the fixed path, loop state, and standalone HTML output.

## Project structure

```text
src/story.twee       Twine/Twee story source and styles
scripts/setup.ps1    Downloads and verifies Tweego
scripts/build.ps1    Exports the standalone HTML file
scripts/test.ps1     Runs stage-one automated checks
dist/index.html      Playable build output
```

## Next stage (not implemented)

Once the fixed loop is stable, the project can add a free-text action box, a lightweight Python backend, the DeepSeek API, and a mechanism that turns promising player ideas into reusable Twine choices.

