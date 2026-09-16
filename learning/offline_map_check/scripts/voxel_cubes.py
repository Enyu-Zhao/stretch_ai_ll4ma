"""Turn DynaMem's voxel map into solid cube meshes that MeshLab / rerun draw as real voxels.

DynaMem stores its map as a sparse *voxelized point cloud*: one averaged point (+colour, +feature)
per occupied voxel. This script snaps those points to their voxel and emits a cube per voxel.

    ./run.sh /work/voxel_cubes.py lab_map_3 [lab_map_2 ...]

Needs /work/out/<run>_voxel.ply and <run>_semantic.ply from voxel_map_view.py.
Writes /work/out/<run>_cubes_height.ply, <run>_cubes_rgb.ply, <run>_cubes.rrd
"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.cm as cm
import numpy as np
import open3d as o3d
import rerun as rr

OUT = "/work/out"

# a unit cube as 6 separate faces (4 verts each) so every face shades flat and edges stay crisp
_F = np.array([
    [[0,0,0],[1,0,0],[1,1,0],[0,1,0]], [[0,0,1],[0,1,1],[1,1,1],[1,0,1]],   # bottom, top
    [[0,0,0],[0,0,1],[1,0,1],[1,0,0]], [[0,1,0],[1,1,0],[1,1,1],[0,1,1]],   # -y, +y
    [[0,0,0],[0,1,0],[0,1,1],[0,0,1]], [[1,0,0],[1,0,1],[1,1,1],[1,1,0]],   # -x, +x
], dtype=np.float64).reshape(24, 3)
_T = np.array([[i, i+1, i+2] for i in range(0, 24, 4)] + [[i, i+2, i+3] for i in range(0, 24, 4)])


def cubes(pts, cols, size, gap=0.08):
    """Snap points to a `size` grid; one cube per occupied cell, average colour."""
    idx = np.floor(pts / size).astype(np.int64)
    uniq, inv = np.unique(idx, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    col = np.zeros((len(uniq), 3))
    np.add.at(col, inv, cols)
    col /= np.bincount(inv)[:, None]
    s = size * (1 - gap)                      # small gap so neighbouring cubes stay distinguishable
    origin = uniq * size + size * gap / 2
    V = (origin[:, None, :] + _F[None] * s).reshape(-1, 3)
    T = (_T[None] + 24 * np.arange(len(uniq))[:, None, None]).reshape(-1, 3)
    return uniq, V, T, col


def write_mesh(path, V, T, vcol):
    m = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(V), o3d.utility.Vector3iVector(T))
    m.vertex_colors = o3d.utility.Vector3dVector(np.clip(vcol, 0, 1))
    m.compute_vertex_normals()
    o3d.io.write_triangle_mesh(path, m, write_ascii=False)


for name in sys.argv[1:] or ["lab_map_3"]:
    vox = o3d.io.read_point_cloud(f"{OUT}/{name}_voxel.ply")
    p, c = np.asarray(vox.points), np.asarray(vox.colors)
    p, c = p[p[:, 2] < 1.5], c[p[:, 2] < 1.5]          # the planner ignores anything above obs_max_height

    cells, V, T, col = cubes(p, c, 0.10)
    z = (cells[:, 2] + 0.5) * 0.10
    zc = cm.turbo(np.clip(z / 1.2, 0, 1))[:, :3]         # colour by height: floor blue -> 1.2 m red

    write_mesh(f"{OUT}/{name}_cubes_height.ply", V, T, np.repeat(zc, 24, axis=0))
    write_mesh(f"{OUT}/{name}_cubes_rgb.ply", V, T, np.repeat(col, 24, axis=0))

    sem = o3d.io.read_point_cloud(f"{OUT}/{name}_semantic.ply")
    _, sV, sT, scol = cubes(np.asarray(sem.points), np.asarray(sem.colors), 0.05)

    rr.init(f"dynamem_cubes_{name}", spawn=False)
    rr.save(f"{OUT}/{name}_cubes.rrd")
    rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    rr.log("world/origin", rr.Arrows3D(vectors=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                                       colors=[[255, 0, 0], [0, 255, 0], [0, 0, 255]]), static=True)
    rr.log("world/obstacle_voxels_by_height", rr.Mesh3D(vertex_positions=V, triangle_indices=T,
                                                       vertex_colors=np.repeat(zc, 24, axis=0)), static=True)
    rr.log("world/obstacle_voxels_rgb", rr.Mesh3D(vertex_positions=V, triangle_indices=T,
                                                 vertex_colors=np.repeat(col, 24, axis=0)), static=True)
    rr.log("world/semantic_voxels_rgb", rr.Mesh3D(vertex_positions=sV, triangle_indices=sT,
                                                 vertex_colors=np.repeat(scol, 24, axis=0)), static=True)
    print(f"{name}: {len(cells)} obstacle cubes @0.10 m, {len(sV)//24} semantic cubes @0.05 m "
          f"-> {name}_cubes_height.ply, {name}_cubes_rgb.ply, {name}_cubes.rrd")
