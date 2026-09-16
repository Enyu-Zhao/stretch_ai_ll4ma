# Mission: DynaMem in stretch_ai

> **Status: DRAFT.** Written from a one-line request ("I want to know the Dynamem part in this repo").
> Confirm or correct the *Why* below in your next session; every lesson is steered by it.

## Why
Understand how DynaMem is implemented in this repo well enough to run it on a Stretch robot, read its
behaviour when something goes wrong, and change it (thresholds, grounding strategy, exploration, manipulation
backend) with confidence rather than by trial and error.

## Success looks like
- Trace "pick up A and place it on B" from `run_dynamem.py` down to the voxel map and back, naming the file and function at each hop.
- Explain, without notes, why DynaMem keeps two point clouds and how the memory stays correct when objects move.
- Predict what a config or flag change (`--mllm`, `--cpu`, `voxel_size`, feature thresholds) will do before running it.
- Know exactly where to edit to swap the visual-grounding strategy, the exploration heuristic, or the grasping backend.

## Constraints
- Learn from the code in this repo and the DynaMem paper first; other sources only when those are silent.
- Short lessons (10-15 min) that end with a concrete win.
- Unknown: whether a robot is available for hands-on practice. Assume "read and modify code" until told otherwise.

## Out of scope (for now)
- The EQA (embodied question answering) module layered on the same voxel map.
- The Discord bot front end.
- AnyGrasp internals in `third_party/ok-robot` (treated as a black box that returns grasp poses).
