# DynaMem runbook

How to start DynaMem again on this setup: robot `stretch-re2-2060` + workstation `Jarvis`, driven from a laptop over SSH.

| Machine | Address | User | stretch_ai checkout |
|---|---|---|---|
| Robot (`stretch-re2-2060`) | `stretch-re2-2060.uconnect.utah.edu` | `hello-robot` | `~/repos/stretch_ai` |
| Workstation (`Jarvis`) | `10.18.170.51` | `enyu` | `~/code/stretch_ai` |

Robot side runs the ROS2 bridge in Docker. Jarvis runs DynaMem in the `stretch-ai-dynamem:local` container (GPU, repo mounted at `/app`, deps pre-installed).

---

## 1. Connect

Two terminals from your laptop:

```bash
# Terminal A: Jarvis, WITH X forwarding (uppercase -Y). The -L ports let you open rerun's web viewer.
ssh -Y -L 9090:localhost:9090 -L 9877:localhost:9877 enyu@10.18.170.51

# Terminal B: robot
ssh hello-robot@stretch-re2-2060.uconnect.utah.edu
```

The robot gets its IP from campus Wi-Fi, and it can change after a reboot. Use the hostname everywhere; it follows the robot. (`getent hosts stretch-re2-2060.uconnect.utah.edu` shows the current IP.)

On Jarvis, confirm the display is forwarded:
```bash
echo $DISPLAY        # must print something like localhost:10.0 — if empty, reconnect with -Y
```

## 2. Robot: home and start the bridge server (Terminal B)

1. Power on the robot. Clear the area around it; homing moves the lift, arm and gripper.
2. Home it (once per power-on):
   ```bash
   stretch_free_robot_process.py
   stretch_robot_home.py
   ```
3. Make sure no bridge server is already running:
   ```bash
   docker ps          # if a stretch-ai-ros2-bridge container is "Up", use it or: docker stop <id>
   ```
4. Start the server and leave this terminal open:
   ```bash
   cd ~/repos/stretch_ai
   ./scripts/run_stretch_ai_ros2_bridge_server.sh
   ```
   Ready when the robot beeps twice, the lidar spins, and the log shows `Starting to send full state`.
   (Add `--update` only if you want to pull a newer image, ~18 GB.)

## 3. Jarvis: check the link and start the container (Terminal A)

```bash
for p in 4401 4402 4403 4404; do timeout 2 bash -c "</dev/tcp/stretch-re2-2060.uconnect.utah.edu/$p" 2>/dev/null && echo "$p open" || echo "$p CLOSED"; done

~/code/stretch_ai/learning/run_dynamem_container.sh
```

You land in `(stretch_ai) root@Jarvis:/app#`. No `pip install` needed. Everything below runs **inside the container**. To open a second shell in the same container: `docker exec -it dynamem bash` from Jarvis.

## 4. Optional: smoke test

```bash
python -m stretch.app.view_images --robot_ip stretch-re2-2060.uconnect.utah.edu
```
The gripper opens, the arm moves, and camera windows appear on your laptop. Click a window and press `q` to quit.

## 5. Optional: drive out of a tight spot

```bash
python -m stretch.app.keyboard_teleop --robot_ip stretch-re2-2060.uconnect.utah.edu
```
**Click the "Robot View" window first** (otherwise keys go to the terminal). One key per move, and wait for each to finish:

| Key | Motion |
|---|---|
| `w` / `s` | forward / back 15 cm |
| `a` / `d` | turn left / right ~14° |
| `q` | quit (required before starting DynaMem) |

No obstacle checking. Watch the robot, not just the camera view.

## 6. Run DynaMem

Before starting:
- **Space:** give it at least a robot's width of clear space on every side. It first spins 360° in place to build its map.
- **Floor:** clear low objects. Anything under 20 cm tall (cables, shoes, chair bases) is not treated as an obstacle.
- **People:** keep them out of the path. It does not react to things that move in front of it while driving.
- **Runstop:** keep it within reach.

```bash
# fresh map (spins in place first)
python -m stretch.app.run_dynamem --robot_ip stretch-re2-2060.uconnect.utah.edu --visual-servo

# name the saved map (→ dynamem_log/<name>)
python -m stretch.app.run_dynamem --robot_ip stretch-re2-2060.uconnect.utah.edu --visual-servo --output-path lab_map

# reuse a saved map, skipping the startup spin (path to the .pkl, relative to /app)
python -m stretch.app.run_dynamem --robot_ip stretch-re2-2060.uconnect.utah.edu --visual-servo --input-path dynamem_log/debug_2026-09-14_22-30-25.pkl
```

At each round it asks `Enter desired mode [E / M]`:
- `E`: explore and map (`--explore-iter N` sets how many iterations; default 3)
- `M`: pick and place. It asks for the target object, then the receptacle.

It asks before each navigate / pick / place step. Answer `N` to skip one. Add `-S` to skip confirmations, only once you trust the setup.

To watch the map: if the output shows `Hosting a web-viewer at http://localhost:9090...`, open that URL on your laptop. The `-L` ports from step 1 make it reachable.

### If something goes wrong

1. **Press the runstop.**
2. **Stop DynaMem before releasing the runstop:** `Ctrl-C` in the container. If it won't exit, run `docker exec dynamem pkill -f run_dynamem` from Jarvis. Otherwise the robot can resume its goal when released.
3. Move the robot clear (you can push it by hand while runstopped), then release the runstop by pressing and briefly holding it.

## 7. Shut down

1. Container: quit the app (`q` / `Ctrl-C`), then `exit`. The container deletes itself.
2. Robot terminal: `Ctrl-C` to stop the bridge server.
3. Power off the robot as usual.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Container script: `$DISPLAY is not set` | SSH connected without X forwarding (`-x` disables it) | Reconnect with `ssh -Y` |
| `X11 connection rejected because of wrong authentication` | Container started from a different SSH session than the current one (display and cookie change per login) | `exit` the container and rerun `run_dynamem_container.sh` from the current session |
| App prints image shapes, then no windows and no error (frozen) | PyAV (`av`) installed; its bundled X libraries deadlock OpenCV windows | `pip uninstall -y av` (already removed in `stretch-ai-dynamem:local`) |
| `ModuleNotFoundError: No module named 'sam2'` | SAM2 missing (the stock image never had it) | `SAM2_BUILD_CUDA=0 pip install -e /app/third_party/segment-anything-2` |
| `a container named 'dynamem' already exists` | Previous container still running | `docker exec -it dynamem bash`, or `docker rm -f dynamem` |
| Teleop key pressed, robot doesn't move | Keys going to the terminal, or runstop on | Click the Robot View window; check the runstop light. Robot log should show `Sending XYT Goal` |
| Port check shows `CLOSED` | Bridge server not running or still starting | Check Terminal B; restart the server |
| `ping` to the robot fails, DynaMem hangs after `Loaded owl model` | Robot's IP changed (reboot) and an old IP was used | Use the hostname `stretch-re2-2060.uconnect.utah.edu`, not an IP |
| rerun: `Failed to bind to WebSocket port 9877` | Another stretch app still running in the container | Quit it first (`q` / `Ctrl-C`) |
| Files in `dynamem_log/` owned by root | Container runs as root | `docker run --rm -v ~/code/stretch_ai/dynamem_log:/log stretch-ai-dynamem:local rm -rf /log/<name>` or `sudo chown -R enyu dynamem_log` |
| Model weights download again on every start | Container started without the cache mount (older launcher script) | Use the current `run_dynamem_container.sh`, which mounts `~/.cache/dynamem-docker` at `/root/.cache` |
| Download stuck at `reconstructing file ... kB/s` | Hugging Face's xet downloader is very slow on this network | `export HF_HUB_DISABLE_XET=1` (the launcher script already sets it), then rerun |
| DynaMem drove into something | See the limits in step 6 | Check the look-around frames in `dynamem_log/debug_*/rgbN.jpg`: each look-around saves 4 frames that should show 4 different directions |
| `AttributeError: 'BaseModelOutputWithPooling' object has no attribute 'norm'` during `M` (navigation) | transformers 5.x makes `get_text_features`/`get_image_features` return an output object, not a tensor; DynaMem's siglip encoder assumed a tensor | Patched in `src/stretch/perception/encoders/siglip{,2}_encoder.py` via `_as_embedding()` (uncommitted local change — survives `git pull` only if not overwritten). Crash is at query time, so the map `.pkl` is already saved: restart with `--input-path dynamem_log/<name>.pkl` |
| `WGPU error: Failed to create surface for any enabled backend` / `Exiting because of error ... during event Resumed` | rerun's native viewer can't get a GPU surface over X forwarding; the viewer window dies | Non-fatal — DynaMem keeps running, you just lose the 3D view (followed by harmless `Broken pipe` / `Dropping messages` warnings). Use the forwarded web viewer (ports in step 1) instead of the native window |

## Rebuilding the local image

Only needed after a `git pull` that changes `src/setup.py`, or if the image is lost.

```bash
# Jarvis: start a container from the stock image
~/code/stretch_ai/learning/run_dynamem_container.sh hellorobotinc/stretch-ai_cuda-11.8:latest

# inside it
pip install -e src
pip uninstall -y av
SAM2_BUILD_CUDA=0 pip install -e /app/third_party/segment-anything-2

# second Jarvis terminal, while that container is still running (it pauses during the commit)
docker commit dynamem stretch-ai-dynamem:local
```

## Where things live

| What | Where |
|---|---|
| Calibrated URDF (DynaMem-patched) | `src/stretch/config/urdf/stretch.urdf` (stock copy: `stretch.urdf.stock`) |
| Saved maps and debug frames | `dynamem_log/` |
| Model weights (Hugging Face etc.), kept across container restarts | `~/.cache/dynamem-docker` on Jarvis → `/root/.cache` in the container |
| SAM2 checkpoint | `sam2.1_hiera_small.pt` in the repo root |
| Container launcher | `learning/run_dynamem_container.sh` |
| Robot hostname / SSH user | `~/.stretch/dynamem.env` |
