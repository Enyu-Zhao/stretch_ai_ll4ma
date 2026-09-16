# DynaMem visualization runbook

How to check a DynaMem run offline, without the robot: whether the map is sound, whether an object made it into semantic memory, and how to view the 3D maps. Companion to [dynamem_runbook.md](dynamem_runbook.md), which covers running DynaMem itself.

Everything here runs on **Jarvis**. The robot doesn't need to be on. Each analysis runs in its own throwaway container, so it's safe to use while a DynaMem session is live (except the rerun viewer; see step 6).

---

## 1. What DynaMem saves

A run started with `--output-path <name>` writes to `~/code/stretch_ai/dynamem_log/`:

| Path | Contents | Written when |
|---|---|---|
| `<name>/rgbN.npy`, `depthN.npy`, `intrinsicsN.npy`, `poseN.npy` | Every observation: RGB, depth (m), camera K, camera-to-world pose | Every frame, including explore rounds |
| `<name>/rgbN.jpg` | Same RGB as a viewable image | Every frame |
| `<name>/rgb<query>_<obs>.png` | The image the object search matched for a text query | Only when a text search actually ran |
| `<name>.pkl` | Saved map (poses, frames, semantic memory) | Only after the startup spin and after a **successful** object search. **Never after explore rounds.** |

So the frame folder is always complete, but the `.pkl` often holds only the 8 startup-spin frames. Every tool below reads the frame folder by default.

## 2. What DynaMem builds

| Structure | Resolution | Stores | Used for |
|---|---|---|---|
| `voxel_pcd` | 0.1 m | position, colour | Navigation: flattened to a 2D obstacle/explored grid for A* and frontiers |
| `semantic_memory` | 0.05 m | position, colour, SigLIP feature, image ID | Finding objects: text query → best voxel → image ID |
| `observations` | per frame | RGB, depth, K, pose | Re-running OWLv2 on the matched image to get a precise 3D point |

Both voxel maps are **voxelized point clouds**: one averaged point per occupied voxel, with empty space not stored. That's why raw exports look like sparse dots. Manipulation uses no map, only the single target point plus live cameras.

## 3. One-time setup

The tools live in `~/dynamem_offline/` (a copy is kept in `learning/offline_map_check/scripts/`).

```bash
mkdir -p ~/dynamem_offline/data ~/dynamem_offline/out
cp ~/code/stretch_ai/learning/offline_map_check/scripts/* ~/dynamem_offline/
```

`run.sh` starts `stretch-ai-dynamem:local` with the GPU, the repo at `/app`, the model cache (offline), and `~/dynamem_offline` at `/work`. Scripts read `/work/data/<name>` and write to `/work/out/`.

| Script | Needs GPU models | Produces |
|---|---|---|
| `map_check.py` | no | geometry check, top-down view, frame montage |
| `semantic_check.py` | SigLIP + OWLv2 | object detection and semantic-memory queries |
| `voxel_map_view.py` | SigLIP | DynaMem's actual voxel maps, 2D planner map, `.ply`, `.rrd` |
| `voxel_cubes.py` | no | solid-cube meshes for MeshLab/rerun (needs `voxel_map_view.py` output) |
| `drift.py` | no | alignment between two runs (paths hardcoded; see step 5) |

## 4. Bring a run in

```bash
cd ~/dynamem_offline
cp -r ~/code/stretch_ai/dynamem_log/lab_map_4 data/
cp ~/code/stretch_ai/dynamem_log/lab_map_4.pkl data/      # only needed for FROM_PKL=1
chmod -R u+w data
```

Copy rather than read `dynamem_log/` in place: a live run can rewrite its `.pkl`.

## 5. Run the analyses

All commands from `~/dynamem_offline`. Several run names can be given at once.

### Geometry: is the map sound?

```bash
./run.sh /work/map_check.py lab_map_4 | tee map_check_lab_map_4.log
```

| Output | What it shows |
|---|---|
| `<name>_topdown.png` | Left: points 0.3–1.8 m high, colour = frame index. Middle: same points in RGB. Right: floor height vs distance. |
| `<name>_montage.jpg` | Every frame, numbered. Find which frames show your object. |
| log table | Per-frame camera pose, floor height, and cross-frame residual |

A healthy map shows camera height a constant 1.30 m and pitch about −34°, floor median within a few cm of 0, and **overall median residual 1–2 cm**. Doubled walls in two colours in the left panel mean pose errors.

### Semantic memory: can it find the object?

```bash
OBJECT="Mustard bottle" RECEPTACLE="black cabinet" ./run.sh /work/semantic_check.py lab_map_4 | tee sem_lab_map_4.log
```

Use exactly the text you typed into DynaMem. Defaults are `pink elephant` / `wood table`. `EXTRA="a,b"` adds more queries.

| Output | What it shows |
|---|---|
| `<name>_owl_best_object.jpg`, `_receptacle.jpg` | OWLv2's best detection across all frames, with score |
| `<name>_similarity.png` | Semantic memory coloured by SigLIP similarity to each query. Red star = best voxel, magenta × = OWLv2 detection. |
| log: `OWLv2 per-frame best score` | Top frames per query, **RGB vs BGR** score, depth in the box |
| log: `Replicating localize_with_feature_similarity` | What DynaMem's own search returns, as coded (BGR) and with RGB |

Read it in this order:
1. **OWLv2 score** above 0.15 on some frame means the detector can see it.
2. **SigLIP argmax** landing near the × means semantic memory holds it.
3. **Replication** returning a point, not `None`, means DynaMem's search would succeed.

If `as coded (BGR)` is `None` but `with RGB` gives a point, you've hit the colour-swap bug (see troubleshooting).

### Voxel maps

```bash
./run.sh /work/voxel_map_view.py lab_map_4
FROM_PKL=1 ./run.sh /work/voxel_map_view.py lab_map_4     # the saved .pkl instead of the frames
./run.sh /work/voxel_cubes.py lab_map_4                   # run after voxel_map_view.py
```

| Output | What it is |
|---|---|
| `<name>_voxel3d.png` | Obstacle voxels from three angles, camera path in red |
| `<name>_2dmap.png` | What the planner sees: dilated obstacles, explored area, and which frame last saw each cell |
| `<name>_voxel.ply` | Obstacle map, one point per voxel (metres) |
| `<name>_semantic.ply` | Semantic memory, one point per voxel (metres) |
| `<name>.rrd` | Both maps and the camera path as points, for rerun |
| **`<name>_cubes_height.ply`** | **Obstacle map as solid cubes, coloured by height. Start here.** |
| `<name>_cubes_rgb.ply` | Same cubes in camera colour (mostly grey carpet) |
| `<name>_cubes.rrd` | Height cubes, RGB cubes and semantic cubes as meshes, plus a 1 m axis marker at the start pose |

### Drift between two runs

Only meaningful when the robot wasn't restarted between runs, so both share one odometry frame. The run names are hardcoded on lines 13 and 17 of `drift.py`; edit them, then:

```bash
./run.sh /work/drift.py
```

A median of 1–2 cm means the runs line up.

## 6. View the results

### Images (`.png`, `.jpg`)

Copy them to your laptop, or open them over X forwarding:

```bash
scp -r enyu@10.18.170.51:~/dynamem_offline/out ./dynamem_out      # on the laptop
xdg-open ~/dynamem_offline/out/lab_map_4_similarity.png           # on Jarvis, over ssh -Y
```

### rerun recordings (`.rrd`)

Needs the `-L 9090:localhost:9090 -L 9877:localhost:9877` tunnel from the main runbook. **Quit DynaMem first**: it uses the same ports.

```bash
docker run --rm -it --network host -v ~/dynamem_offline/out:/maps \
  stretch-ai-dynamem:local /root/miniforge3/envs/stretch_ai/bin/rerun --web-viewer /maps/lab_map_4_cubes.rrd
```

Open **http://localhost:9090** on your laptop. `Ctrl-C` stops it.

- In `_cubes.rrd`, show only `world/obstacle_voxels_by_height` at first.
- The red/green/blue arrows at `world/origin` are 1 m along x/y/z at the start pose.
- Drag to orbit, scroll to zoom, double-click to recentre.

To view natively on the laptop instead, the version must match: `pip install rerun-sdk==0.18.0`, then `rerun lab_map_4_cubes.rrd`.

### Meshes and point clouds (`.ply`)

Nothing on Jarvis displays these. Copy to the laptop and use **MeshLab** or **CloudCompare** (both free).

1. Open **one file at a time**: File → New Empty Project, then Import Mesh.
2. Render → Shading → Face if the cubes look flat.
3. **Ctrl+H** resets the view when you're lost.
4. **Double-click** a cube to orbit around it; scroll to zoom, right-drag to pan.

To use the data in code rather than view it:

```python
import open3d as o3d, numpy as np
pc = o3d.io.read_point_cloud("lab_map_4_voxel.ply")
xyz, rgb = np.asarray(pc.points), np.asarray(pc.colors)   # metres, world frame; colour 0..1
```

## 7. File results by run

Outputs in `~/dynamem_offline/out/` are root-owned (the container runs as root) but readable. Collect one run into its own folder:

```bash
D=~/code/stretch_ai/learning/offline_map_check/lab_map_4
mkdir -p $D && cp ~/dynamem_offline/out/lab_map_4_* ~/dynamem_offline/out/lab_map_4.rrd $D/
cp ~/dynamem_offline/*lab_map_4*.log $D/ 2>/dev/null
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `AttributeError: 'BaseModelOutputWithPooling' object has no attribute 'norm'` | transformers v5 changed `get_text_features` | Fixed in `src/stretch/perception/encoders/siglip_encoder.py` (`_as_embedding`). **Uncommitted**: don't discard it. |
| `'Owlv2Processor' object has no attribute 'post_process_object_detection'` during grasping | transformers v5 moved the method | Fixed in `owlsam_perception.py` (uses `processor.image_processor`). **Uncommitted.** |
| Object visible in frames but search returns nothing; log shows `as coded (BGR): None` | `voxel_dynamem.py:644` converts RGB→BGR before OWLv2. Yellow/orange objects suffer most (mustard bottle 0.57 → 0.12). | Not fixed yet. Removing that `cvtColor` line fixes it. |
| `semantic_check.py` ignores `OBJECT=` | Env var not forwarded into the container | `run.sh` must include `-e OBJECT -e RECEPTACLE -e EXTRA -e FROM_PKL` |
| `Permission denied` writing a log into `out/` | `out/` was created by the container as root | Write logs to `~/dynamem_offline/` instead, as in the commands above |
| `.pkl` map has only 8 observations | The pickle is saved only after the startup spin and a successful search | Analyse the frame folder (the default), not `FROM_PKL=1` |
| rerun: `Failed to bind to WebSocket port 9877` | DynaMem or another viewer is using the port | Quit it first |
| MeshLab shows a huge regular lattice next to a small blob | An Open3D `VoxelGrid` `.ply`: its vertices are grid indices, not metres | Use `*_cubes_*.ply`. Don't export with `o3d.io.write_voxel_grid`. |
| Open3D window fails or is very slow | OpenGL over `ssh -Y` | View in rerun's web viewer or on the laptop |
| `FileNotFoundError` for `/work/replay/...` | DynaMem's log dir is created with non-recursive `os.mkdir` | The scripts create `/work/replay` first; recreate it if deleted |

## Where things live

| What | Where |
|---|---|
| Offline tools and working data | `~/dynamem_offline/` (`data/` inputs, `out/` results) |
| Copy of the scripts | `learning/offline_map_check/scripts/` |
| Filed results per run | `learning/offline_map_check/lab_map_*/` |
| Raw DynaMem output | `dynamem_log/<name>/` and `dynamem_log/<name>.pkl` |
| Existing repo viewer (other map format, interactive only) | `python -m stretch.app.read_map -i <file>.pkl --show-svm`, documented in `docs/apps.md`. It likely can't read DynaMem pickles. |
