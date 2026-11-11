# creative

A playground for learning agentic automation to create content: apps, websites, games, renders, videos, images and audio.

## Who does what
- **Claude Code (Opus 5.5):** writes scripts, transcripts, storyboards and code, and orchestrates the other tools.
- **Google Flow** (`flow` MCP, via [GTAI-1/flow-mcp](https://github.com/GTAI-1/flow-mcp) cloned in `google-flow/`): images (Imagen / Nano Banana) and video (Veo). It drives the Flow web UI in a dedicated Chrome profile and uses the user's Google account credits.
- **Fish Audio** (`fish-audio` MCP, hosted at `https://api.fish.audio/mcp`, OAuth): voice and audio. Default TTS model: **Drama 3**. Put delivery direction in square brackets before a line, e.g. `[whispering]`, `[excited]`.
- **Blender 5.3** (`blender` MCP, via [MCP for Blender](https://github.com/ahujasid/blender-mcp), run with `uvx mcp-for-blender`, telemetry off): 3D scenes, modeling, renders. Blender must be open with the add-on's server started (N panel → MCP for Blender → Start MCP Server, port 9876). `execute_blender_code` runs arbitrary Python in Blender, so save the .blend before big changes.

## Layout
- `projects/<name>/`: one folder per creation, holding the script, prompts, code and notes. Committed to git.
- `media/<project>/`: generated images, video and audio. Gitignored because the files are large.
- `google-flow/`: third-party flow-mcp clone. Gitignored. Update it with `git -C google-flow pull; npm install; npm run build`.

## Rules for generation
- Credits cost money or are rate-limited. Before any batch generation, state the planned number of generations and the estimated credits, and keep `max_credits` caps in place.
- Check `flow_status` / `get_credit_balance` before large runs.
- Save prompts next to outputs (in `projects/<name>/prompts.md`) so the results can be reproduced.
