# Notes

## Workspace layout
- Workspace lives in `learning/` inside the stretch_ai repo, not the repo root, to keep `git status` clean.
- Lessons link to source with relative paths (`../../src/...`) so they open from the browser or VS Code.
- Glossary not yet created: per the format rules, terms are promoted only after the user demonstrates understanding. Candidates from lesson 1: obstacle cloud, semantic memory, point removal, visual grounding, value-based exploration, observation id.

## Preferences observed
- 2026-09-08: User works over SSH with no local browser. Publish every lesson as a claude.ai Artifact (inline CSS/JS, rewrite `../../` links to GitHub blob URLs, fold the reference doc in as an appendix). Lesson 1 artifact: https://claude.ai/code/artifact/8b4991c5-d2b1-44b7-8132-e30e88c14987
- Build script pattern lives in this session only; regenerate from lessons/ + assets/ when publishing.
- 2026-09-08: User asked to "know the Dynamem part in this repo". No preferences on format stated yet. Mission is a draft; confirm next session.

## Discrepancies between paper and code worth teaching later
- Paper says the robot replans after ~7 waypoints; code chunks trajectories at 8 (`robot_agent_dynamem.py` `process_text`).
- Paper's exploration combines a time value map and a similarity value map; this stack implements only the time heuristic (`voxel_map_dynamem.py` `_time_heuristic`), the similarity heuristic is commented out with a TODO.
- Paper removes voxels closer than 2 m; code uses 2.5 m and a 0.1 m depth margin (`utils/voxel.py` `clear_points`).
- `localize_with_feature_similarity` has a hard-coded fallback threshold of 0.21 that ignores the encoder's `feature_matching_threshold`.

## Lesson backlog (ordered by likely ZPD)
1. Big picture: four calls, two clouds (done: 0001)
2. The memory update: `process_rgbd_images` and `clear_points` line by line
3. Visual grounding: feature-similarity path, then mLLM hybrid path
4. Navigation loop: `process_text`, 8-waypoint chunks, `sample_navigation`, A*
5. Value-based exploration: `get_2d_map` history layer and `_time_heuristic`
6. Manipulation backends: AnyGrasp over ZMQ vs visual servoing
7. Config and flags: `dynav_config.yaml`, CPU mode, thresholds
