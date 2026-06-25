#!/usr/bin/env python3
"""
==============================================================================
ROCm + PyTorch Validation Script for AMD Radeon RX 9070 XT (RDNA 4 / gfx1201)
==============================================================================

This script validates whether PyTorch with ROCm is working correctly on an
AMD Radeon RX 9070 XT GPU. It tests GPU detection, tensor operations, and
CLIP model inference, then reports PASS/FAIL for each check.

Target hardware:
  - AMD Radeon RX 9070 XT (RDNA 4 architecture, gfx1201)
  - 16 GB VRAM, 256-bit bus
  - Windows 11 / WSL2 / Linux

==============================================================================
INSTALLATION GUIDE
==============================================================================

--- Option A: Native Windows (ROCm 7.2.1) [RECOMMENDED] ---

Prerequisites:
  - Windows 11
  - Python 3.12
  - AMD Adrenalin driver 26.2.2 or later
  - RX 9070 XT is officially supported as of ROCm 7.2.1

Step 1 - Install ROCm SDK components (CMD prompt, use ^ for line continuation):

  pip install --no-cache-dir ^
      https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl ^
      https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl ^
      https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl ^
      https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm-7.2.1.tar.gz

Step 2 - Install PyTorch + ROCm (CMD prompt):

  pip install --no-cache-dir ^
      https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl ^
      https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl ^
      https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchvision-0.24.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl

Step 3 - Install inference dependencies:

  pip install open-clip-torch Pillow numpy==1.26.4

Note: numpy 2.x is incompatible with current ROCm torch wheels. Pin to 1.26.4.
Note: In PowerShell, replace ^ with ` (backtick) for line continuation.
Note: PyTorch on Windows includes ROCm 7.2.1 components, but the FULL ROCm
      stack is not yet supported on Windows. PyTorch inference works fine.

--- Option B: WSL2 (Ubuntu on Windows) ---

WSL2 is now a first-class supported platform as of ROCm 7.2. Setup:

  1. Enable WSL2:      wsl --install -d Ubuntu-24.04
  2. Install AMD driver: Adrenalin 26.2.2+ (Windows side, GPU passthrough is automatic)
  3. Inside WSL2 Ubuntu, install ROCm:
       sudo apt update && sudo apt install -y rocm-dev
  4. Install PyTorch:
       pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/rocm7.2
     OR use AMD's tested wheels:
       wget https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2/torch-2.9.1+rocm7.2.0.lw.git7e1940d4-cp312-cp312-linux_x86_64.whl
       pip3 install torch-*.whl
  5. pip3 install open-clip-torch Pillow numpy==1.26.4

Caveat: AMD docs note WSL2 may have lower inference performance than native Linux.

--- Option C: DirectML Fallback (if ROCm fails) ---

DirectML works on ANY DirectX 12 GPU without ROCm. Simpler but ~4x slower.

  pip install torch torchvision torch-directml

Usage: device = torch_directml.device() instead of "cuda"

--- Option D: ONNX Runtime with DirectML ---

  pip install onnxruntime-directml

Good for production inference; export models to ONNX first.

--- Option E: CPU-only fallback ---

  pip install torch torchvision  (no ROCm index)

Slowest option but always works. Viable for small models like CLIP ViT-B/32.

==============================================================================
RDNA 4 / RX 9070 XT ROCm COMPATIBILITY NOTES (as of June 2026)
==============================================================================

- ROCm 6.4.1 (May 2025) was the first release with RDNA 4 (gfx1201) support
  on Linux (Ubuntu 24.04, 22.04, RHEL 9.x).
- ROCm 6.4.4 introduced a public preview of Windows PyTorch support for
  RX 7000/9000 series.
- ROCm 7.2.1 is the current recommended version with production Windows
  support for the RX 9070 XT.
- RDNA 4 supports FP8 natively (unique vs RDNA 3 which only supports FP16).
- Community reports confirm: PyTorch inference, Stable Diffusion, and local
  LLMs all work on RX 9070 XT. Some users report rough edges -- if you hit
  issues, try the HSA_OVERRIDE_GFX_VERSION=12.0.1 environment variable.
- vLLM does not yet have native RDNA 4 kernels; for LLM serving, Vulkan
  backends (llama.cpp) may be faster until kernel support lands.
- For CLIP and YOLOv8 inference (our use case), ROCm works well. ONNX Runtime
  with DirectML is a solid alternative for YOLOv8 specifically.

==============================================================================
"""

import sys
import os
import time
import traceback
from typing import Optional

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def header(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 70}{RESET}\n")


def passed(msg: str) -> None:
    print(f"  {GREEN}[PASS]{RESET} {msg}")


def failed(msg: str, detail: str = "") -> None:
    print(f"  {RED}[FAIL]{RESET} {msg}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"         {line}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[WARN]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}[INFO]{RESET} {msg}")


# ---------------------------------------------------------------------------
# Results tracker
# ---------------------------------------------------------------------------

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    if ok:
        passed(name)
    else:
        failed(name, detail)


# ---------------------------------------------------------------------------
# Check 1: PyTorch import and version
# ---------------------------------------------------------------------------

def check_pytorch_import() -> bool:
    header("Check 1: PyTorch Import")
    try:
        import torch
        info(f"PyTorch version : {torch.__version__}")
        info(f"Python version  : {sys.version.split()[0]}")

        # Check if this is a ROCm build
        hip_available = hasattr(torch.version, "hip") and torch.version.hip is not None
        cuda_version = getattr(torch.version, "cuda", None)

        if hip_available:
            info(f"HIP version     : {torch.version.hip}")
            info(f"Build type      : ROCm (HIP)")
            record("PyTorch imported (ROCm build)", True)
        elif cuda_version:
            info(f"CUDA version    : {cuda_version}")
            warn("This is a CUDA build of PyTorch, not ROCm.")
            warn("ROCm requires the ROCm-specific PyTorch wheel.")
            record("PyTorch imported (CUDA build -- not ROCm)", False,
                   "Install PyTorch ROCm wheel from repo.radeon.com")
        else:
            info("Build type      : CPU-only")
            warn("No GPU acceleration available in this PyTorch build.")
            record("PyTorch imported (CPU-only build)", False,
                   "Install PyTorch ROCm wheel for GPU support")

        return hip_available

    except ImportError as e:
        record("PyTorch import", False, f"ImportError: {e}")
        return False


# ---------------------------------------------------------------------------
# Check 2: GPU detection
# ---------------------------------------------------------------------------

def check_gpu_detection() -> Optional[str]:
    header("Check 2: GPU Detection")
    try:
        import torch

        # ROCm exposes GPUs through the CUDA API in PyTorch
        cuda_available = torch.cuda.is_available()
        info(f"torch.cuda.is_available() = {cuda_available}")

        if not cuda_available:
            record("GPU detection (torch.cuda.is_available)", False,
                   "No GPU detected. Check ROCm installation and driver.")

            # Try to get more diagnostic info
            _print_rocm_diagnostics()
            return None

        device_count = torch.cuda.device_count()
        info(f"Device count    : {device_count}")

        if device_count == 0:
            record("GPU detection (device count)", False, "0 devices found")
            return None

        gpu_name = torch.cuda.get_device_name(0)
        info(f"GPU 0 name      : {gpu_name}")

        # Check memory
        total_mem = torch.cuda.get_device_properties(0).total_memory
        total_mem_gb = total_mem / (1024 ** 3)
        info(f"GPU 0 VRAM      : {total_mem_gb:.1f} GB")

        # Verify it looks like an RX 9070 XT
        is_target_gpu = any(x in gpu_name.lower() for x in ["9070", "gfx1201", "navi 48"])
        if is_target_gpu:
            record("GPU detection (RX 9070 XT found)", True)
        else:
            warn(f"Expected RX 9070 XT but found: {gpu_name}")
            record("GPU detection (GPU found, not RX 9070 XT)", True,
                   f"Detected: {gpu_name}")

        # Try to get GFX version / architecture info
        try:
            arch_list = torch.cuda.get_arch_list()
            info(f"Supported archs : {', '.join(arch_list)}")
        except Exception:
            pass

        try:
            capability = torch.cuda.get_device_capability(0)
            info(f"Compute cap.    : {capability[0]}.{capability[1]}")
        except Exception:
            pass

        return gpu_name

    except Exception as e:
        record("GPU detection", False, f"Error: {e}")
        traceback.print_exc()
        return None


def _print_rocm_diagnostics() -> None:
    """Print extra diagnostic info when GPU detection fails."""
    info("--- Diagnostics ---")

    # Check environment variables
    hsa_override = os.environ.get("HSA_OVERRIDE_GFX_VERSION")
    if hsa_override:
        info(f"HSA_OVERRIDE_GFX_VERSION = {hsa_override}")
    else:
        warn("HSA_OVERRIDE_GFX_VERSION not set.")
        warn("Try: export HSA_OVERRIDE_GFX_VERSION=12.0.1")

    rocr_visible = os.environ.get("ROCR_VISIBLE_DEVICES")
    if rocr_visible:
        info(f"ROCR_VISIBLE_DEVICES = {rocr_visible}")

    hip_visible = os.environ.get("HIP_VISIBLE_DEVICES")
    if hip_visible:
        info(f"HIP_VISIBLE_DEVICES = {hip_visible}")

    # Check if rocm-smi is available
    import shutil
    if shutil.which("rocm-smi"):
        info("rocm-smi found. Run 'rocm-smi' for GPU status.")
    elif shutil.which("rocminfo"):
        info("rocminfo found. Run 'rocminfo' for GPU info.")
    else:
        warn("Neither rocm-smi nor rocminfo found in PATH.")

    # Check for common ROCm paths
    rocm_paths = [
        "/opt/rocm",
        "C:\\Program Files\\AMD\\ROCm",
        os.path.expanduser("~/.local/lib/python3.12/site-packages/rocm_sdk_core"),
    ]
    for p in rocm_paths:
        if os.path.exists(p):
            info(f"ROCm path found : {p}")


# ---------------------------------------------------------------------------
# Check 3: Basic tensor operations on GPU
# ---------------------------------------------------------------------------

def check_tensor_ops() -> bool:
    header("Check 3: Tensor Operations on GPU")
    try:
        import torch

        if not torch.cuda.is_available():
            record("Tensor ops on GPU", False, "No GPU available, skipping.")
            return False

        device = torch.device("cuda:0")

        # Test 1: Create tensor on GPU
        info("Creating 1024x1024 tensor on GPU...")
        a = torch.randn(1024, 1024, device=device)
        b = torch.randn(1024, 1024, device=device)
        record("Tensor creation on GPU", True)

        # Test 2: Matrix multiplication
        info("Running matrix multiplication (1024x1024)...")
        torch.cuda.synchronize()
        start = time.perf_counter()
        c = torch.mm(a, b)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        info(f"MatMul time     : {elapsed * 1000:.2f} ms")
        record("Matrix multiplication on GPU", True)

        # Test 3: Verify result is on GPU and has correct shape
        assert c.device.type == "cuda", f"Result on wrong device: {c.device}"
        assert c.shape == (1024, 1024), f"Wrong shape: {c.shape}"
        record("Result validation (device + shape)", True)

        # Test 4: GPU-to-CPU transfer
        c_cpu = c.cpu()
        assert c_cpu.device.type == "cpu"
        record("GPU-to-CPU transfer", True)

        # Test 5: FP16 support (important for CLIP)
        info("Testing FP16 operations...")
        a_fp16 = a.half()
        b_fp16 = b.half()
        c_fp16 = torch.mm(a_fp16, b_fp16)
        assert c_fp16.dtype == torch.float16
        record("FP16 (half precision) operations", True)

        # Test 6: Larger matmul benchmark
        info("Benchmarking larger matmul (4096x4096, FP16)...")
        a_big = torch.randn(4096, 4096, device=device, dtype=torch.float16)
        b_big = torch.randn(4096, 4096, device=device, dtype=torch.float16)
        # Warmup
        for _ in range(3):
            torch.mm(a_big, b_big)
        torch.cuda.synchronize()
        start = time.perf_counter()
        n_iters = 10
        for _ in range(n_iters):
            torch.mm(a_big, b_big)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / n_iters) * 1000
        info(f"4096x4096 FP16  : {avg_ms:.2f} ms avg ({n_iters} iterations)")

        # Rough TFLOPS estimate
        flops_per_matmul = 2 * 4096 * 4096 * 4096
        tflops = (flops_per_matmul / (avg_ms / 1000)) / 1e12
        info(f"Estimated perf  : {tflops:.1f} TFLOPS (FP16)")
        record("Large matmul benchmark", True)

        return True

    except Exception as e:
        record("Tensor operations on GPU", False, f"Error: {e}")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Check 4: CLIP model loading and inference
# ---------------------------------------------------------------------------

def check_clip_inference() -> bool:
    header("Check 4: CLIP Model Inference (open_clip ViT-B/32)")
    try:
        import torch

        # Determine device
        if torch.cuda.is_available():
            device = torch.device("cuda:0")
            device_label = torch.cuda.get_device_name(0)
        else:
            device = torch.device("cpu")
            device_label = "CPU (fallback)"
            warn("GPU not available, testing on CPU.")

        info(f"Device          : {device_label}")

        # Import open_clip
        try:
            import open_clip
        except ImportError:
            record("CLIP inference (open_clip import)", False,
                   "open_clip not installed. Run: pip install open-clip-torch")
            return False

        info(f"open_clip ver   : {open_clip.__version__}")

        # Load model
        info("Loading CLIP ViT-B-32 (laion2b_s34b_b79k)...")
        load_start = time.perf_counter()
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32",
            pretrained="laion2b_s34b_b79k",
            device=device,
        )
        model.eval()
        load_time = time.perf_counter() - load_start
        info(f"Model load time : {load_time:.2f} s")
        record("CLIP model loaded", True)

        # Create tokenizer
        tokenizer = open_clip.get_tokenizer("ViT-B-32")

        # Create a dummy image (224x224 RGB)
        try:
            from PIL import Image
        except ImportError:
            record("CLIP inference (Pillow import)", False,
                   "Pillow not installed. Run: pip install Pillow")
            return False

        info("Creating dummy test image (224x224)...")
        import numpy as np
        dummy_np = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        dummy_image = Image.fromarray(dummy_np)

        # Preprocess image
        image_input = preprocess(dummy_image).unsqueeze(0).to(device)
        info(f"Image tensor    : {image_input.shape}, dtype={image_input.dtype}")
        record("Image preprocessing", True)

        # Encode image
        info("Running image encoding...")
        if device.type == "cuda":
            torch.cuda.synchronize()
        encode_start = time.perf_counter()

        with torch.no_grad(), torch.amp.autocast(device_type=device.type, enabled=(device.type == "cuda")):
            image_features = model.encode_image(image_input)

        if device.type == "cuda":
            torch.cuda.synchronize()
        encode_time = time.perf_counter() - encode_start
        info(f"Image encode    : {encode_time * 1000:.1f} ms")
        info(f"Embedding shape : {image_features.shape}")
        record("CLIP image encoding", True)

        # Encode text
        info("Running text encoding...")
        test_labels = ["a red t-shirt", "blue jeans", "white sneakers", "black jacket", "floral dress"]
        text_tokens = tokenizer(test_labels).to(device)

        if device.type == "cuda":
            torch.cuda.synchronize()
        text_start = time.perf_counter()

        with torch.no_grad(), torch.amp.autocast(device_type=device.type, enabled=(device.type == "cuda")):
            text_features = model.encode_text(text_tokens)

        if device.type == "cuda":
            torch.cuda.synchronize()
        text_time = time.perf_counter() - text_start
        info(f"Text encode     : {text_time * 1000:.1f} ms  ({len(test_labels)} labels)")
        info(f"Text emb shape  : {text_features.shape}")
        record("CLIP text encoding", True)

        # Compute similarity
        info("Computing image-text similarity...")
        image_features_norm = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features_norm = text_features / text_features.norm(dim=-1, keepdim=True)
        similarity = (image_features_norm @ text_features_norm.T).squeeze(0)
        probs = similarity.softmax(dim=-1).cpu().numpy()

        info("Similarity scores (random image, for validation only):")
        for label, prob in zip(test_labels, probs):
            info(f"  {label:20s} : {prob:.4f}")
        record("CLIP similarity computation", True)

        # Benchmark: multiple inference passes
        info("Benchmarking inference (10 passes)...")
        if device.type == "cuda":
            # Warmup
            for _ in range(3):
                with torch.no_grad():
                    model.encode_image(image_input)
            torch.cuda.synchronize()

        n_bench = 10
        bench_start = time.perf_counter()
        for _ in range(n_bench):
            with torch.no_grad():
                model.encode_image(image_input)
        if device.type == "cuda":
            torch.cuda.synchronize()
        bench_elapsed = time.perf_counter() - bench_start
        avg_inference_ms = (bench_elapsed / n_bench) * 1000

        info(f"Avg inference   : {avg_inference_ms:.1f} ms/image ({n_bench} passes)")
        info(f"Throughput      : {1000 / avg_inference_ms:.0f} images/sec")
        record("CLIP inference benchmark", True)

        # Memory usage
        if device.type == "cuda":
            mem_allocated = torch.cuda.memory_allocated(0) / (1024 ** 2)
            mem_reserved = torch.cuda.memory_reserved(0) / (1024 ** 2)
            info(f"GPU mem alloc   : {mem_allocated:.0f} MB")
            info(f"GPU mem reserved: {mem_reserved:.0f} MB")

        return True

    except Exception as e:
        record("CLIP inference", False, f"Error: {e}")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Check 5: DirectML fallback test (optional)
# ---------------------------------------------------------------------------

def check_directml_fallback() -> bool:
    header("Check 5: DirectML Fallback (optional)")
    try:
        import torch_directml
        dml_device = torch_directml.device()
        info(f"DirectML device : {dml_device}")

        import torch
        t = torch.randn(256, 256, device=dml_device)
        r = torch.mm(t, t)
        assert r.shape == (256, 256)
        record("DirectML available and working", True)
        return True
    except ImportError:
        info("torch-directml not installed (optional fallback).")
        info("Install with: pip install torch-directml")
        record("DirectML availability", False, "Not installed (optional)")
        return False
    except Exception as e:
        record("DirectML test", False, f"Error: {e}")
        return False


# ---------------------------------------------------------------------------
# Summary and fallback instructions
# ---------------------------------------------------------------------------

def print_summary(gpu_detected: bool, tensor_ops_ok: bool, clip_ok: bool) -> None:
    header("SUMMARY")

    total = len(results)
    passes = sum(1 for _, ok, _ in results if ok)
    fails = total - passes

    print(f"  Total checks  : {total}")
    print(f"  {GREEN}Passed{RESET}        : {passes}")
    print(f"  {RED}Failed{RESET}        : {fails}")
    print()

    if fails == 0:
        print(f"  {GREEN}{BOLD}All checks passed! ROCm + PyTorch is working on your GPU.{RESET}")
        print(f"  Your RX 9070 XT is ready for CLIP and YOLOv8 inference.")
    elif gpu_detected and clip_ok:
        print(f"  {YELLOW}{BOLD}Mostly working. Review the failed checks above.{RESET}")
    elif gpu_detected and tensor_ops_ok:
        print(f"  {YELLOW}{BOLD}GPU compute works but CLIP inference failed.{RESET}")
        print(f"  Check open_clip installation and model download.")
    elif not gpu_detected:
        print(f"  {RED}{BOLD}GPU not detected. ROCm is not working.{RESET}")
        print()
        _print_fallback_instructions()


def _print_fallback_instructions() -> None:
    print(f"  {BOLD}--- Troubleshooting Steps ---{RESET}")
    print()
    print(f"  1. {BOLD}Check driver:{RESET} Install AMD Adrenalin 26.2.2+")
    print(f"     Download: https://www.amd.com/en/support")
    print()
    print(f"  2. {BOLD}Set environment variable:{RESET}")
    print(f"     Windows CMD : set HSA_OVERRIDE_GFX_VERSION=12.0.1")
    print(f"     PowerShell  : $env:HSA_OVERRIDE_GFX_VERSION='12.0.1'")
    print(f"     Linux/WSL2  : export HSA_OVERRIDE_GFX_VERSION=12.0.1")
    print()
    print(f"  3. {BOLD}Verify ROCm PyTorch wheel:{RESET}")
    print(f"     python -c \"import torch; print(torch.version.hip)\"")
    print(f"     Should print a HIP version, not None.")
    print()
    print(f"  4. {BOLD}Try WSL2 (often more reliable):{RESET}")
    print(f"     wsl --install -d Ubuntu-24.04")
    print(f"     # Inside WSL2:")
    print(f"     pip3 install --pre torch torchvision --index-url \\")
    print(f"         https://download.pytorch.org/whl/nightly/rocm7.2")
    print()
    print(f"  {BOLD}--- Fallback Options (if ROCm cannot be fixed) ---{RESET}")
    print()
    print(f"  Option A: {BOLD}DirectML{RESET} (~4x slower than ROCm, but works on any DX12 GPU)")
    print(f"    pip install torch torchvision torch-directml")
    print(f"    Usage: device = torch_directml.device()")
    print()
    print(f"  Option B: {BOLD}ONNX Runtime + DirectML{RESET} (good for production inference)")
    print(f"    pip install onnxruntime-directml")
    print(f"    Export models to ONNX format first.")
    print()
    print(f"  Option C: {BOLD}CPU inference{RESET} (slowest, but always works)")
    print(f"    pip install torch torchvision")
    print(f"    CLIP ViT-B/32 runs at ~50-100ms/image on Ryzen 7 7700.")
    print()
    print(f"  Option D: {BOLD}Vulkan backend{RESET} (via llama.cpp for LLMs)")
    print(f"    Best for LLM inference on RDNA 4 until vLLM adds gfx1201 kernels.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    header("ROCm Validation for AMD Radeon RX 9070 XT")

    info(f"Platform        : {sys.platform}")
    info(f"Python          : {sys.version.split()[0]}")
    info(f"Working dir     : {os.getcwd()}")

    # Check HSA override
    hsa = os.environ.get("HSA_OVERRIDE_GFX_VERSION", "")
    if hsa:
        info(f"HSA_OVERRIDE    : {hsa}")
    else:
        info("HSA_OVERRIDE    : (not set)")

    # Run checks
    is_rocm = check_pytorch_import()
    gpu_name = check_gpu_detection()
    gpu_detected = gpu_name is not None
    tensor_ops_ok = check_tensor_ops()
    clip_ok = check_clip_inference()

    # Optional DirectML check (only if ROCm failed or always for info)
    if not gpu_detected:
        check_directml_fallback()

    # Summary
    print_summary(gpu_detected, tensor_ops_ok, clip_ok)

    # Return exit code
    fails = sum(1 for _, ok, _ in results if not ok)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
