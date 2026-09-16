"""Render DynaMem's actual voxel map offline: obstacle voxels, semantic voxels, 2D planner map.

Usage (inside the container via run.sh):
    ./run.sh /work/voxel_map_view.py lab_map_3
    FROM_PKL=1 ./run.sh /work/voxel_map_view.py lab_map_3     # use the saved .pkl instead of the frames

Outputs to /work/out/<run>_*:  voxel.ply, semantic.ply, voxel3d.png, 2dmap.png, .rrd
"""
import glob
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import open3d as o3d
import rerun as rr
import torch

sys.path.insert(0, "/app/src")
from stretch.core.parameters import get_parameters
from stretch.mapping.voxel.voxel_dynamem import SparseVoxelMap
from stretch.perception.encoders.siglip_encoder import MaskSiglipEncoder

OUT = "/work/out"
os.makedirs(OUT, exist_ok=True)
os.makedirs("/work/replay", exist_ok=True)
torch.manual_seed(0)
np.random.seed(0)

params = get_parameters("dynav_config.yaml")
VOXEL = params["voxel_size"]          # 0.1 m, the obstacle map resolution
encoder = MaskSiglipEncoder(version="so400m", feature_matching_threshold=0.14, device="cuda")


def build(name, from_pkl=False):
    vm = SparseVoxelMap(
        resolution=VOXEL,
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
        detection=None,
        encoder=encoder,
        image_shape=(480, 360),
        log=f"/work/replay/{name}_voxview",
        mllm=False,
        run_eqa=False,
    )
    poses = []
    if from_pkl:
        vm.read_from_pickle(f"/work/data/{name}.pkl")
        poses = [np.asarray(f.camera_pose) for f in vm.observations]
    else:
        d = f"/work/data/{name}"
        ids = sorted(int(re.findall(r"pose(\d+)", f)[0]) for f in glob.glob(d + "/pose*.npy"))
        for i in ids:
            pose = np.load(f"{d}/pose{i}.npy")
            vm.process_rgbd_images(
                np.load(f"{d}/rgb{i}.npy"),
                np.load(f"{d}/depth{i}.npy"),
                np.load(f"{d}/intrinsics{i}.npy"),
                pose,
            )
            poses.append(pose)
    return vm, np.array(poses)


def save_ply(path, pts, rgb01):
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(np.asarray(pts, dtype=np.float64))
    pc.colors = o3d.utility.Vector3dVector(np.clip(np.asarray(rgb01, dtype=np.float64), 0, 1))
    o3d.io.write_point_cloud(path, pc)
    return len(pc.points)


def render(name, from_pkl=False):
    vm, poses = build(name, from_pkl)

    # ---- obstacle voxel map (what the planner consumes) ----
    xyz, _, counts, _ = vm.voxel_pcd.get_pointcloud()
    xyz = xyz.cpu().numpy()
    vrgb = vm.voxel_pcd._rgb.cpu().numpy() / 255.0
    print(f"{name}: obstacle voxel map {len(xyz)} voxels @ {VOXEL} m; "
          f"extent x[{xyz[:,0].min():.1f},{xyz[:,0].max():.1f}] "
          f"y[{xyz[:,1].min():.1f},{xyz[:,1].max():.1f}] z[{xyz[:,2].min():.1f},{xyz[:,2].max():.1f}]")

    # ---- semantic voxel map ----
    spts, _, _, _ = vm.semantic_memory.get_pointcloud()
    spts = spts.cpu().numpy()
    srgb = vm.semantic_memory._rgb.cpu().numpy() / 255.0

    n1 = save_ply(f"{OUT}/{name}_voxel.ply", xyz, vrgb)
    n2 = save_ply(f"{OUT}/{name}_semantic.ply", spts, srgb)
    print(f"  wrote {name}_voxel.ply ({n1} pts), {name}_semantic.ply ({n2} pts)")

    # ---- true cube geometry as a mesh, so it reads as voxels not dots ----
    vg = o3d.geometry.VoxelGrid.create_from_point_cloud(
        o3d.io.read_point_cloud(f"{OUT}/{name}_voxel.ply"), voxel_size=VOXEL
    )
    o3d.io.write_voxel_grid(f"{OUT}/{name}_voxelgrid.ply", vg)
    print(f"  wrote {name}_voxelgrid.ply ({len(vg.get_voxels())} cubes)")

    # ---- static 3D previews ----
    fig = plt.figure(figsize=(21, 7))
    for k, (elev, azim, title) in enumerate(
        [(90, -90, "top"), (25, -60, "oblique"), (5, 0, "side")]
    ):
        ax = fig.add_subplot(1, 3, k + 1, projection="3d")
        keep = xyz[:, 2] < params["obs_max_height"]
        ax.scatter(xyz[keep, 0], xyz[keep, 1], xyz[keep, 2], c=vrgb[keep], s=2, marker="s")
        ax.plot(poses[:, 0, 3], poses[:, 1, 3], poses[:, 2, 3], "-o", c="red", ms=2, lw=1)
        ax.view_init(elev=elev, azim=azim)
        ax.set_box_aspect((np.ptp(xyz[:, 0]), np.ptp(xyz[:, 1]), max(np.ptp(xyz[:, 2]), 1)))
        ax.set_title(f"{name}: obstacle voxels @ {VOXEL} m ({title})")
    plt.tight_layout()
    plt.savefig(f"{OUT}/{name}_voxel3d.png", dpi=100)
    plt.close()

    # ---- the 2D map the planner actually plans on ----
    obstacles, explored, history = vm.get_2d_map(return_history_id=True)
    # crop to the region the robot actually mapped (the grid is 1024x1024 cells)
    occ = explored.numpy() | obstacles.numpy()
    occ[:35] = occ[-35:] = False
    occ[:, :35] = occ[:, -35:] = False
    xs, ys = np.nonzero(occ)
    pad = 15
    x0, x1 = max(0, xs.min() - pad), xs.max() + pad
    y0, y1 = max(0, ys.min() - pad), ys.max() + pad
    crop = lambda a: a[x0:x1, y0:y1]
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))
    for ax, img, t in [
        (axes[0], crop(obstacles.numpy()), "obstacles (dilated, what A* avoids)"),
        (axes[1], crop(explored.numpy()), "explored"),
        (axes[2], crop(history.numpy()), "history: most recent obs id per cell"),
    ]:
        im = ax.imshow(img.T, origin="lower")
        plt.colorbar(im, ax=ax, fraction=0.046)
        ax.set_title(f"{name}: {t}")
    grid = np.array([vm.xy_to_grid_coords(p[:2, 3]).numpy() for p in poses])
    for ax in axes:
        ax.plot(grid[:, 0] - x0, grid[:, 1] - y0, "-o", c="red", ms=3, lw=1)
    plt.tight_layout()
    plt.savefig(f"{OUT}/{name}_2dmap.png", dpi=100)
    plt.close()

    # ---- interactive rerun recording ----
    rr.init(f"dynamem_{name}", spawn=False)
    rr.save(f"{OUT}/{name}.rrd")
    rr.log("world/obstacle_voxels", rr.Points3D(xyz, colors=vrgb, radii=VOXEL / 2))
    rr.log("world/semantic_voxels", rr.Points3D(spts, colors=srgb, radii=0.025))
    rr.log("world/camera_path", rr.LineStrips3D([poses[:, :3, 3]], colors=[255, 0, 0]))
    print(f"  wrote {name}.rrd, {name}_voxel3d.png, {name}_2dmap.png")


for n in sys.argv[1:] or ["lab_map_3"]:
    render(n, from_pkl=bool(os.environ.get("FROM_PKL")))
