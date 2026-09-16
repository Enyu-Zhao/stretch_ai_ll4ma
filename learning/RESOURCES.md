# DynaMem Resources

## Knowledge

- [Paper: "DynaMem: Online Dynamic Spatio-Semantic Memory for Open World Mobile Manipulation" (Liu et al., 2024)](https://arxiv.org/abs/2411.04999)
  Primary source. HTML version at https://arxiv.org/html/2411.04999. Use for: the add/remove voxel rule, the three query strategies (VL feature, mLLM, hybrid), the value-based exploration formulas, and the DynaBench ablations (removal 70.6% vs 67.8% without; hybrid k=3 74.5%).
- [Project site: dynamem.github.io](https://dynamem.github.io)
  Videos and overview. Use for: seeing the intended behaviour before reading code.
- [Repo doc: docs/dynamem.md](../docs/dynamem.md)
  The maintainers' own description of the code structure, run commands, CPU vs GPU model table, and calibration caveats. Use for: how to launch, which flags exist, what changes on CPU.
- [Repo doc: docs/llm_agent.md](../docs/llm_agent.md)
  The non-DynaMem Stretch AI agent DynaMem is contrasted with. Use for: understanding what visual servoing manipulation is when `--visual-servo` is set.
- [Code: src/stretch/mapping/voxel/voxel_dynamem.py](../src/stretch/mapping/voxel/voxel_dynamem.py)
  The memory itself. Use for: `process_rgbd_images`, `localize_text`, pickle save/load.
- [Code: src/stretch/utils/voxel.py](../src/stretch/utils/voxel.py)
  `VoxelizedPointcloud.clear_points` is the point-removal rule from the paper, implemented. Use for: the exact depth/ray test and the DBSCAN cleanup.
- [OK-Robot repo and docs](https://github.com/ok-robot/ok-robot)
  The predecessor system; DynaMem reuses its AnyGrasp manipulation pipeline. Use for: workspace install for AnyGrasp, URDF calibration doc.
- [AnyGrasp SDK](https://github.com/graspnet/anygrasp_sdk)
  Closed-source grasp pose predictor. Use for: licence registration only.
- [Paper: OWLv2 "Scaling Open-Vocabulary Object Detection" (Minderer et al., 2023)](https://arxiv.org/abs/2306.09683)
  The detector used to confirm a match inside the retrieved image. Use for: why detection is a second check after feature similarity.
- [Paper: SigLIP "Sigmoid Loss for Language Image Pre-Training" (Zhai et al., 2023)](https://arxiv.org/abs/2303.15343)
  The encoder producing per-pixel features on GPU. Use for: what the cosine-similarity thresholds are comparing.

## Wisdom (Communities)

- [Hello Robot forum](https://forum.hello-robot.com)
  Official Stretch community, staff answer. Use for: calibration, ROS2 bridge, robot-side problems.
- [stretch_ai GitHub issues](https://github.com/hello-robot/stretch_ai/issues)
  Where DynaMem-specific bugs and questions land. Use for: checking whether a failure is known before debugging it.

## Gaps
- No verified, active community specifically about DynaMem beyond GitHub issues. The paper authors (NYU, Lerrel Pinto's lab) are the practitioners; their GitHub is the closest thing.
- No trustworthy source found yet on tuning the SigLIP/CLIP feature thresholds beyond the two numbers in the code (0.14 GPU, 0.35 CPU).
