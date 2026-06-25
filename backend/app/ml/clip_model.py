import logging

import open_clip
import torch
from PIL import Image

logger = logging.getLogger(__name__)

_model = None
_preprocess = None
_tokenizer = None
_device = None


def load_clip(model_name: str = "ViT-B-32", pretrained: str = "openai"):
    global _model, _preprocess, _tokenizer, _device

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _model, _, _preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained, device=_device
    )
    _tokenizer = open_clip.get_tokenizer(model_name)
    _model.eval()
    logger.info("CLIP %s loaded on %s", model_name, _device)


def encode_image(image: Image.Image) -> list[float]:
    """Encode a PIL image into a 512-dimensional embedding vector."""
    if _model is None:
        raise RuntimeError("CLIP model not loaded. Call load_clip() first.")

    image_tensor = _preprocess(image).unsqueeze(0).to(_device)
    with torch.no_grad():
        features = _model.encode_image(image_tensor)
        features /= features.norm(dim=-1, keepdim=True)
    return features[0].cpu().tolist()
