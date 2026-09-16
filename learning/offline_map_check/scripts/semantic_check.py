"""Replay DynaMem debug frames through the real semantic-memory code and query it offline.

For each run:
  * rebuild SparseVoxelMap exactly as RobotAgent.create_obstacle_map (GPU, non-mllm branch)
  * query SigLIP semantic memory, replicate localize_with_feature_similarity (BGR as in code, and RGB)
  * sweep OWLv2 over every frame with per-query scores (RGB vs BGR), check depth in box
  * query the saved .pkl semantic memory (startup-spin only) too
"""
import glob
import json
import os
import re
import sys

import cv2
import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, "/app/src")
from stretch.core.parameters import get_parameters
from stretch.mapping.voxel.voxel_dynamem import SparseVoxelMap
from stretch.perception.detection.owl import OwlPerception
from stretch.perception.encoders.siglip_encoder import MaskSiglipEncoder
from stretch.utils.image import Camera, camera_xyz_to_global_xyz

OUT = "/work/out"
os.makedirs(OUT, exist_ok=True)
os.makedirs("/work/replay", exist_ok=True)
torch.manual_seed(0)
np.random.seed(0)

RUNS = sys.argv[1:] or ["lab_map_0", "lab_map_1"]

# What to look for. Override per run, e.g.
#   OBJECT="Mustard bottle" RECEPTACLE="black cabinet" ./run.sh /work/semantic_check.py lab_map_3
OBJECT = os.environ.get("OBJECT", "pink elephant")
RECEPTACLE = os.environ.get("RECEPTACLE", "wood table")
EXTRA = [q for q in os.environ.get("EXTRA", "").split(",") if q]

OWL_QUERIES = [OBJECT, OBJECT.lower(), RECEPTACLE, RECEPTACLE.lower()] + EXTRA
OWL_QUERIES = list(dict.fromkeys(OWL_QUERIES))  # de-duplicate, keep order
SIGLIP_QUERIES = OWL_QUERIES + ["a photo of a " + OBJECT.lower()]

params = get_parameters("dynav_config.yaml")
device = "cuda"
encoder = MaskSiglipEncoder(version="so400m", feature_matching_threshold=0.14, device=device)
owl = OwlPerception(version="owlv2-L-p14-ensemble", device=device, confidence_threshold=0.15)

# --- tokenizer sanity (transformers v5) ---
tok = encoder.tokenizer(["Pink elephant"], padding="max_length", return_tensors="pt")
print("SigLIP tokenizer: input_ids shape", tuple(tok["input_ids"].shape), "model_max_length", encoder.tokenizer.model_max_length)
print("  ids(Pink elephant)", tok["input_ids"][0][:8].tolist(), " ids(pink elephant)", encoder.tokenizer(["pink elephant"])["input_ids"][0][:8])


def make_map(log):
    return SparseVoxelMap(
        resolution=params["voxel_size"],
        semantic_memory_resolution=0.05,
        local_radius=params["local_radius"],
        obs_min_height=params["obs_min_height"],
        obs_max_height=params["obs_max_height"],
        obs_min_density=params["obs_min_density"],
        grid_resolution=0.1,
        min_depth=params["min_depth"],
        max_depth=params["max_depth"],
        pad_obstacles=params["pad_obstacles"],
        add_local_radius_points=params.get("add_local_radius_points", default=True),
        remove_visited_from_obstacles=params.get("remove_visited_from_obstacles", default=False),
        smooth_kernel_size=params.get("filters/smooth_kernel_size", -1),
        use_median_filter=params.get("filters/use_median_filter", False),
        median_filter_size=params.get("filters/median_filter_size", 5),
        use_derivative_filter=params.get("filters/use_derivative_filter", False),
        derivative_filter_threshold=params.get("filters/derivative_filter_threshold", 0.5),
        detection=owl,
        encoder=encoder,
        image_shape=(480, 360),
        log=log,
        mllm=False,
        run_eqa=False,
    )


def owl_scores(rgb_hwc_uint8, queries):
    """Per-query best score + box for one image (no threshold)."""
    img = torch.from_numpy(rgb_hwc_uint8).permute(2, 0, 1)
    texts = ["a photo of a " + q for q in queries]
    inputs = owl.processor(text=[texts], images=img, return_tensors="pt").to(device)
    with torch.no_grad():
        out = owl.model(**inputs)
    probs = torch.sigmoid(out.logits[0])  # [N, Q]
    H, W = rgb_hwc_uint8.shape[:2]
    m = max(H, W)
    cx, cy, w, h = out.pred_boxes[0].unbind(-1)
    boxes = torch.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], -1) * m
    res = {}
    for qi, q in enumerate(queries):
        j = probs[:, qi].argmax()
        res[q] = (probs[j, qi].item(), boxes[j].tolist())
    return res


def box_depth_stats(depth, box):
    H, W = depth.shape
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    d = depth[y0:y1, x0:x1]
    if d.size == 0:
        return None
    dv = d[d > 0]
    return dict(
        min=float(dv.min()) if dv.size else 0.0,
        med=float(np.median(dv)) if dv.size else 0.0,
        frac_valid_sem=float(((d > 0.25) & (d < 2.5)).mean()),
        px=int(d.size),
    )


def box_xyz(f, box):
    depth = f["depth"]
    H, W = depth.shape
    cam = Camera.from_K(f["K"], width=W, height=H)
    xyz = camera_xyz_to_global_xyz(cam.depth_to_xyz(depth), f["pose"])
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    return np.median(xyz[y0:y1, x0:x1].reshape(-1, 3), axis=0)


def query_memory(vm, q, gt=None):
    points, _, _, _ = vm.semantic_memory.get_pointcloud()
    al = vm.find_alignment_over_model(q).cpu()[0]
    pts = points.detach().cpu()
    obs = vm.semantic_memory._obs_counts.detach().cpu()
    k = al.argmax()
    r = dict(max_sim=al.max().item(), argmax_xyz=[round(v, 2) for v in pts[k].tolist()], argmax_obs=int(obs[k]))
    # top observations by per-frame max alignment
    per = {}
    for o in obs.unique().tolist():
        per[o] = al[obs == o].max().item()
    r["top_obs"] = sorted(per.items(), key=lambda x: -x[1])[:5]
    r["top_obs"] = [(int(o), round(s, 3)) for o, s in r["top_obs"]]
    if gt is not None:
        d = torch.linalg.norm(pts - torch.tensor(gt, dtype=pts.dtype), dim=-1)
        near = d < 0.15
        r["n_pts_within_15cm_of_gt"] = int(near.sum())
        if near.any():
            nm = al[near].max().item()
            r["best_sim_near_gt"] = round(nm, 3)
            r["rank_of_best_near_gt"] = int((al > nm).sum()) + 1
        r["argmax_dist_to_gt"] = round(d[k].item(), 2)
    return r


def load_frames(d):
    ids = sorted(int(re.findall(r"pose(\d+)", f)[0]) for f in glob.glob(d + "/pose*.npy"))
    return [
        dict(
            i=i,
            rgb=np.load(f"{d}/rgb{i}.npy"),
            depth=np.load(f"{d}/depth{i}.npy"),
            K=np.load(f"{d}/intrinsics{i}.npy"),
            pose=np.load(f"{d}/pose{i}.npy"),
        )
        for i in ids
    ]


report = {}
for name in RUNS:
    print(f"\n==================== {name} ====================")
    frames = load_frames(f"/work/data/{name}")

    # ---------- OWL sweep over all frames ----------
    sweep = {q: [] for q in OWL_QUERIES}
    for f in frames:
        s_rgb = owl_scores(f["rgb"], OWL_QUERIES)
        s_bgr = owl_scores(np.ascontiguousarray(f["rgb"][:, :, ::-1]), OWL_QUERIES)
        for q in OWL_QUERIES:
            sweep[q].append((f["i"], s_rgb[q], s_bgr[q]))
    print("\nOWLv2 per-frame best score (threshold in code = 0.15). Top 5 frames per query:")
    for q in OWL_QUERIES:
        top = sorted(sweep[q], key=lambda x: -x[1][0])[:5]
        print(f"  '{q}':")
        for i, (sr, br), (sb, bb) in top:
            ds = box_depth_stats(frames[i - 1]["depth"], br)
            print(
                f"     frame {i:2d}  RGB {sr:.3f}  BGR {sb:.3f}   box={[int(v) for v in br]}  depth min/med {ds['min']:.2f}/{ds['med']:.2f} m  in-range(0.25-2.5) {ds['frac_valid_sem']:.2f}"
            )

    # ground truth elephant / table location from best RGB detection
    gts = {}
    for key, q in [("object", OBJECT.lower()), ("receptacle", RECEPTACLE.lower())]:
        i, (sr, br), _ = max(sweep[q], key=lambda x: x[1][0])
        gts[key] = box_xyz(frames[i - 1], br).tolist()
        vis = cv2.cvtColor(frames[i - 1]["rgb"].copy(), cv2.COLOR_RGB2BGR)
        cv2.rectangle(vis, (int(br[0]), int(br[1])), (int(br[2]), int(br[3])), (0, 255, 0), 3)
        cv2.putText(vis, f"{q} {sr:.2f}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        cv2.imwrite(f"{OUT}/{name}_owl_best_{key}.jpg", vis)
        print(f"  GT-ish {key} from frame {i} (score {sr:.2f}): xyz = {np.round(gts[key], 2).tolist()}")

    # ---------- replay into semantic memory ----------
    vm = make_map(f"/work/replay/{name}")
    for f in frames:
        vm.process_rgbd_images(f["rgb"], f["depth"], f["K"], f["pose"])
    pts, _, _, _ = vm.semantic_memory.get_pointcloud()
    print(f"\nReplayed semantic memory: {len(pts)} points from {len(frames)} frames")

    print("\nSigLIP semantic-memory queries (full replay, all frames):")
    for q in SIGLIP_QUERIES:
        gt = gts["object"] if OBJECT.lower().split()[-1] in q.lower() else (gts["receptacle"] if RECEPTACLE.lower().split()[-1] in q.lower() else None)
        r = query_memory(vm, q, gt)
        print(f"  '{q}': {json.dumps(r)}")

    # ---------- replicate localize_with_feature_similarity ----------
    print("\nReplicating localize_with_feature_similarity (obs from SigLIP argmax, then OWL on that one frame):")
    for q in [OBJECT, RECEPTACLE]:
        al = vm.find_alignment_over_model(q).cpu()
        obs_id = int(vm.semantic_memory._obs_counts[al.argmax(dim=-1)].item())
        fr = vm.observations[obs_id - 1]
        rgb_bgr = cv2.cvtColor(fr.rgb.numpy(), cv2.COLOR_RGB2BGR)  # exactly as in the code
        res_code = owl.compute_obj_coord(q, rgb_bgr, fr.depth, fr.camera_K, fr.camera_pose)
        res_rgb = owl.compute_obj_coord(q, fr.rgb.numpy(), fr.depth, fr.camera_K, fr.camera_pose)
        print(
            f"  '{q}': SigLIP argmax obs={obs_id} max_sim={al.max().item():.3f} (>0.21 fallback: {al.max().item() > 0.21})"
            f"\n      OWL as coded (BGR): {None if res_code is None else np.round(res_code.tolist(), 2).tolist()}"
            f"\n      OWL with RGB      : {None if res_rgb is None else np.round(res_rgb.tolist(), 2).tolist()}"
        )

    # ---------- the saved pkl (startup spin only) ----------
    vm_pkl = make_map(f"/work/replay/{name}_pkl")
    vm_pkl.read_from_pickle(f"/work/data/{name}.pkl")
    print(f"\nSaved {name}.pkl semantic memory: {len(vm_pkl.semantic_memory._points)} points, {len(vm_pkl.observations)} observations")
    for q in [OBJECT, RECEPTACLE]:
        gt = gts["object"] if OBJECT.lower().split()[-1] in q.lower() else gts["receptacle"]
        print(f"  '{q}': {json.dumps(query_memory(vm_pkl, q, gt))}")

    # ---------- similarity heat map (top-down) ----------
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(20, 7))
    P = pts.detach().cpu().numpy()
    RGB = vm.semantic_memory._rgb.detach().cpu().numpy() / 255.0
    axes[0].scatter(P[:, 0], P[:, 1], s=1, c=RGB)
    axes[0].set_title(f"{name}: replayed semantic memory (RGB)")
    for ax, q, key in [(axes[1], OBJECT, "object"), (axes[2], RECEPTACLE, "receptacle")]:
        al = vm.find_alignment_over_model(q).cpu()[0].numpy()
        o = np.argsort(al)
        sc = ax.scatter(P[o, 0], P[o, 1], s=2, c=al[o], cmap="viridis")
        k = al.argmax()
        ax.scatter([P[k, 0]], [P[k, 1]], marker="*", s=300, c="red", label=f"argmax {al[k]:.3f}")
        ax.scatter([gts[key][0]], [gts[key][1]], marker="x", s=200, c="magenta", label="OWL best detection")
        ax.legend()
        ax.set_title(f"SigLIP similarity: '{q}'")
        plt.colorbar(sc, ax=ax)
    for ax in axes:
        ax.set_aspect("equal")
    plt.tight_layout()
    plt.savefig(f"{OUT}/{name}_similarity.png", dpi=100)
    plt.close()
