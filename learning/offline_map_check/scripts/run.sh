#!/usr/bin/env bash
# Run a python script in a throwaway container (no robot, no host network), cached weights, offline.
exec docker run --rm --gpus all -v /home/enyu/code/stretch_ai:/app -v /home/enyu/.cache/dynamem-docker:/root/.cache -v /home/enyu/dynamem_offline:/work -e FROM_PKL -e OBJECT -e RECEPTACLE -e EXTRA -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e PYTHONUNBUFFERED=1 -w /work stretch-ai-dynamem:local /root/miniforge3/envs/stretch_ai/bin/python "$@"
