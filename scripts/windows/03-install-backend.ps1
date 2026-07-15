# Install the backend venv with ROCm 7.2.1 PyTorch (RX 9070 XT / gfx1201).
# ROCm wheels go in FIRST so requirements.txt doesn't pull CPU torch.
$ErrorActionPreference = "Stop"
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location (Join-Path $repo "backend")

$pyVersion = (py -3.12 --version) 2>$null
if (-not $pyVersion) { Write-Error "Python 3.12 not found — ROCm torch wheels are cp312-only. Install from python.org." }
Write-Host "Using $pyVersion"

if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
$python = ".\.venv\Scripts\python.exe"

& $python -m pip install --upgrade pip

Write-Host "Installing ROCm 7.2.1 SDK components..." -ForegroundColor Cyan
& $python -m pip install --no-cache-dir `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl

Write-Host "Installing PyTorch + ROCm wheels..." -ForegroundColor Cyan
& $python -m pip install --no-cache-dir `
    "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl" `
    "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl" `
    "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/torchvision-0.24.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl"

Write-Host "Installing app requirements..." -ForegroundColor Cyan
& $python -m pip install -r requirements.txt

# numpy 2.x is incompatible with current ROCm torch wheels.
& $python -m pip install "numpy==1.26.4"

$hip = & $python -c "import torch; print(torch.version.hip)"
if ($hip -eq "None" -or -not $hip) {
    Write-Host "WARNING: torch is NOT a ROCm build (torch.version.hip=None). requirements.txt may have replaced it — rerun the PyTorch wheel install above with --force-reinstall." -ForegroundColor Yellow
} else {
    Write-Host "torch ROCm build OK (HIP $hip)." -ForegroundColor Green
}

Write-Host "Downloading YOLOv8 DeepFashion2 weights..." -ForegroundColor Cyan
& $python ..\scripts\download_weights.py

Write-Host "Done. Validate the GPU with: backend\.venv\Scripts\python.exe scripts\validate_rocm.py" -ForegroundColor Green
