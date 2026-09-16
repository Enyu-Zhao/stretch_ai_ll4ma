"""Offline geometric sanity check of DynaMem debug frames: poses, floor, cross-frame consistency."""
import glob
import os
import re
import sys

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

OUT = "/work/out"
os.makedirs(OUT, exist_ok=True)


def load_run(d):
    ids = sorted(int(re.findall(r"pose(\d+)", f)[0]) for f in glob.glob(d + "/pose*.npy"))
    fr = []
    for i in ids:
        fr.append(
            dict(
                i=i,
                rgb=np.load(f"{d}/rgb{i}.npy"),
                depth=np.load(f"{d}/depth{i}.npy"),
                K=np.load(f"{d}/intrinsics{i}.npy"),
                pose=np.load(f"{d}/pose{i}.npy"),
            )
        )
    return fr


def backproject(f, dmin=0.25, dmax=4.0, step=4):
    depth = f["depth"][::step, ::step]
    K = f["K"]
    H, W = depth.shape
    v, u = np.mgrid[0:H, 0:W]
    u = u * step
    v = v * step
    z = depth
    m = (z > dmin) & (z < dmax)
    x = (u - K[0, 2]) * z / K[0, 0]
    y = (v - K[1, 2]) * z / K[1, 1]
    cam = np.stack([x[m], y[m], z[m], np.ones(m.sum())], -1)
    w = cam @ f["pose"].T
    return w[:, :3], f["rgb"][::step, ::step][m], z[m]


def yaw_of(pose):
    fwd = pose[:3, 2]
    return np.arctan2(fwd[1], fwd[0])


def analyze(name):
    fr = load_run(f"/work/data/{name}")
    print(f"\n===== {name}: {len(fr)} frames =====")
    print(" i   cam_x  cam_y  cam_z  yaw(deg) pitch(deg)  valid<2.5m  floor_z_med  floor_z_iqr  floor_slope(m/m)")
    clouds = []
    for f in fr:
        P = f["pose"]
        fwd = P[:3, 2]
        pitch = np.degrees(np.arcsin(fwd[2]))
        w, c, z = backproject(f)
        clouds.append((w, c))
        valid = ((f["depth"] > 0.25) & (f["depth"] < 2.5)).mean()
        # floor: points below 0.15 m
        fl = w[w[:, 2] < 0.15]
        if len(fl) > 50:
            rng = np.linalg.norm(fl[:, :2] - P[:2, 3], axis=1)
            slope = np.polyfit(rng, fl[:, 2], 1)[0]
            q1, med, q3 = np.percentile(fl[:, 2], [25, 50, 75])
            fs = f"{med:+.3f}      {q3-q1:.3f}        {slope:+.3f}"
        else:
            fs = "n/a (no floor in view)"
        print(
            f"{f['i']:2d}  {P[0,3]:+.2f}  {P[1,3]:+.2f}  {P[2,3]:.2f}   {np.degrees(yaw_of(P)):+7.1f}  {pitch:+6.1f}     {valid:.2f}       {fs}"
        )

    # Cross-frame consistency: each frame's points vs. union of all OTHER frames, only in overlap.
    print(" cross-frame residual (points with a neighbour <0.20 m in other frames): median / p90 NN distance, overlap frac")
    res_all = []
    for k, (w, _) in enumerate(clouds):
        others = np.concatenate([clouds[j][0] for j in range(len(clouds)) if j != k])
        # voxel-downsample others for speed
        tree = cKDTree(others)
        d, _ = tree.query(w, k=1)
        ov = d < 0.20
        if ov.sum() > 100:
            res_all.append(np.median(d[ov]))
            print(f"   frame {fr[k]['i']:2d}: {np.median(d[ov])*100:.1f} cm / {np.percentile(d[ov],90)*100:.1f} cm, overlap {ov.mean():.2f}")
    print(f" overall median residual {np.median(res_all)*100:.1f} cm")

    # Top-down view colored by frame, walls only (0.3-1.8 m)
    fig, axes = plt.subplots(1, 3, figsize=(21, 7))
    cmap = plt.get_cmap("turbo")
    for k, (w, c) in enumerate(clouds):
        s = (w[:, 2] > 0.3) & (w[:, 2] < 1.8)
        axes[0].scatter(w[s, 0], w[s, 1], s=0.3, color=cmap(k / max(1, len(clouds) - 1)))
        axes[1].scatter(w[s, 0], w[s, 1], s=0.3, c=c[s] / 255.0)
    for ax in axes[:2]:
        for k, f in enumerate(fr):
            P = f["pose"]
            fwd = P[:3, 2]
            ax.arrow(P[0, 3], P[1, 3], 0.3 * fwd[0], 0.3 * fwd[1], head_width=0.05, color="k")
            ax.text(P[0, 3] + 0.35 * fwd[0], P[1, 3] + 0.35 * fwd[1], str(f["i"]), fontsize=7)
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
    axes[0].set_title(f"{name}: points 0.3-1.8 m high, colour = frame index (blue early, red late)")
    axes[1].set_title("same, true RGB")
    # side view: z vs horizontal range for floor points, colored by frame
    for k, (w, c) in enumerate(clouds):
        P = fr[k]["pose"]
        s = w[:, 2] < 0.3
        rng = np.linalg.norm(w[s, :2] - P[:2, 3], axis=1)
        axes[2].scatter(rng, w[s, 2], s=0.3, color=cmap(k / max(1, len(clouds) - 1)))
    axes[2].axhline(0, color="k", lw=0.5)
    axes[2].set_xlabel("horizontal distance from camera (m)")
    axes[2].set_ylabel("z (m)")
    axes[2].set_title("floor points: z vs range (should be flat at 0)")
    plt.tight_layout()
    plt.savefig(f"{OUT}/{name}_topdown.png", dpi=110)
    plt.close()

    # Montage of RGB frames
    thumbs = []
    for f in fr:
        im = cv2.resize(f["rgb"], (240, 320))
        im = cv2.cvtColor(im, cv2.COLOR_RGB2BGR)
        cv2.putText(im, str(f["i"]), (5, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        thumbs.append(im)
    cols = 8
    while len(thumbs) % cols:
        thumbs.append(np.zeros_like(thumbs[0]))
    rows = [np.hstack(thumbs[r : r + cols]) for r in range(0, len(thumbs), cols)]
    cv2.imwrite(f"{OUT}/{name}_montage.jpg", np.vstack(rows))


for n in sys.argv[1:] or ["lab_map_0", "lab_map_1"]:
    analyze(n)
