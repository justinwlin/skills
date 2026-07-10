# Dual-mode Runpod image (pod dev + serverless), built on an official Runpod base
# so torch/CUDA already match Runpod hosts. Swap the base with --build-arg:
#   docker build --platform linux/amd64 -t <you>/whisper-dualmode:v1 . --push
# See README_BUILD-style matrix in the golden path for other torch/CUDA tags.
ARG BASE_IMAGE=runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    MODE_TO_RUN=${MODE_TO_RUN:-pod} \
    WORKSPACE_DIR=/app

WORKDIR $WORKSPACE_DIR

# Install deps first so the layer caches across handler edits.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY handler.py start.sh ./
RUN chmod +x start.sh

CMD ["./start.sh"]
