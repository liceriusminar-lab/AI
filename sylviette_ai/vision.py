"""
sylviette_ai/vision.py
──────────────────────
CLIP визуальный энкодер для Сильфиетты.
Позволяет модели "видеть" картинки.
"""

import torch
import open_clip
from PIL import Image
from pathlib import Path


class VisionEncoder:
    """
    Загружает CLIP и кодирует картинки в эмбеддинги
    которые понимает SylvietteGPT.
    """

    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "openai",
                 device: str = "cuda"):
        self.device = device
        print(f"✦ Загружаем CLIP {model_name}...")
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        self.model = self.model.to(device).eval()
        self.dim   = 512  # размер эмбеддинга ViT-B-32
        print(f"  ✓ CLIP загружен! Размерность: {self.dim}")

    @torch.no_grad()
    def encode(self, image) -> torch.Tensor:
        """
        Кодирует картинку в эмбеддинг.
        image: путь к файлу (str/Path) или PIL.Image
        Возвращает: [1, 512] тензор
        """
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")
        elif not isinstance(image, Image.Image):
            raise ValueError("image должен быть путём к файлу или PIL.Image")

        tensor = self.preprocess(image).unsqueeze(0).to(self.device)
        features = self.model.encode_image(tensor)
        features = features / features.norm(dim=-1, keepdim=True)  # нормализация
        return features.float()

    @torch.no_grad()
    def encode_bytes(self, image_bytes: bytes) -> torch.Tensor:
        """Кодирует картинку из байтов (для HTTP запросов)."""
        import io
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return self.encode(image)

    def describe_size(self, image) -> str:
        """Возвращает размер картинки."""
        if isinstance(image, (str, Path)):
            image = Image.open(image)
        return f"{image.width}×{image.height}"


# Глобальный экземпляр (загружается один раз)
_vision_encoder = None

def get_vision_encoder(device: str = "cuda") -> VisionEncoder:
    global _vision_encoder
    if _vision_encoder is None:
        _vision_encoder = VisionEncoder(device=device)
    return _vision_encoder


if __name__ == "__main__":
    # Тест
    enc = VisionEncoder(device="cuda" if torch.cuda.is_available() else "cpu")
    print(f"✓ VisionEncoder работает!")
    print(f"  Размерность эмбеддинга: {enc.dim}")

    # Тест с тестовой картинкой
    img = Image.new("RGB", (224, 224), color=(100, 150, 200))
    emb = enc.encode(img)
    print(f"  Тест эмбеддинга: {emb.shape} | norm: {emb.norm().item():.4f}")
    print("✓ Vision готов!")
