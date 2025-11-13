import io
import os
import threading
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from PIL import Image

try:
    import torch
    from torchvision import models, transforms
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise RuntimeError(
        "PyTorch and torchvision are required for the cat recognition module. "
        "Please install them via `pip install torch torchvision`."
    ) from exc


def _default_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():  # type: ignore[attr-defined]
        return "mps"
    return "cpu"


def _resolve_model_path(model_dir: str, model_filename: str) -> Optional[str]:
    candidate = os.path.join(model_dir, model_filename)
    return candidate if os.path.exists(candidate) else None


def _bits_to_hex(bits: np.ndarray) -> str:
    """Convert boolean array to a hex string."""
    packed = np.packbits(bits.astype(np.uint8))
    return packed.tobytes().hex()


def hex_to_bits(hex_string: str, length: Optional[int] = None) -> np.ndarray:
    """Convert stored hex string back to boolean numpy array."""
    if not hex_string:
        return np.array([], dtype=bool)
    data = bytes.fromhex(hex_string)
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    if length is not None and bits.size > length:
        bits = bits[:length]
    return bits.astype(bool)


def hamming_distance(hash_a: np.ndarray, hash_b: np.ndarray) -> int:
    """Return Hamming distance between two bit arrays."""
    if hash_a.size == 0 or hash_b.size == 0:
        return 9999
    min_len = min(hash_a.size, hash_b.size)
    return int(np.count_nonzero(hash_a[:min_len] != hash_b[:min_len]) + abs(hash_a.size - hash_b.size))


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    if vec_a.size == 0 or vec_b.size == 0:
        return 0.0
    denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denom == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / denom)


@dataclass
class RecognitionResult:
    cat_id: Optional[int]
    cat_name: str
    similarity: float
    hamming_distance: int
    reference_image_id: Optional[int]
    reference_hash_length: int
    matched: bool
    metadata: Dict[str, float]


class CatFaceRecognizer:
    """
    Cat face recognition service that loads a CNN backbone (ResNet18 by default)
    to compute embeddings and locality-sensitive hashes for cat images.
    """

    def __init__(
        self,
        model_dir: str = "models/cat_face",
        model_filename: str = "cat_resnet18.pth",
        device: Optional[str] = None,
        hash_length: Optional[int] = None,
    ):
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)

        self.model_filename = model_filename
        self.model_path = _resolve_model_path(self.model_dir, self.model_filename)
        self.device = torch.device(device or _default_device())
        self.hash_length_override = hash_length

        self._model = None
        self._model_lock = threading.Lock()

        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )

    def _load_model(self) -> torch.nn.Module:
        with self._model_lock:
            if self._model is not None:
                return self._model

            backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
            backbone.fc = torch.nn.Identity()

            if self.model_path:
                try:
                    state_dict = torch.load(self.model_path, map_location="cpu")
                    backbone.load_state_dict(state_dict, strict=False)
                    print(f"Loaded cat face weights from {self.model_path}")
                except Exception as exc:  # pragma: no cover
                    print(f"Failed to load custom cat face weights: {exc}. Falling back to ImageNet weights.")

            backbone.eval()
            backbone.to(self.device)
            self._model = backbone
            return self._model

    def set_model_weights(self, model_path: str) -> None:
        if not os.path.exists(model_path):
            raise FileNotFoundError(model_path)
        with self._model_lock:
            self.model_path = model_path
            self._model = None

    def embedding_dim(self) -> int:
        model = self._load_model()
        dummy = torch.zeros(1, 3, 224, 224)
        with torch.no_grad():
            output = model(dummy.to(self.device))
        return int(output.shape[1])

    def _compute_embedding(self, image: Image.Image) -> np.ndarray:
        image = image.convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)
        model = self._load_model()
        with torch.no_grad():
            embedding = model(tensor).cpu().numpy().flatten()
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm

    def compute_signature(self, image_bytes: bytes) -> Tuple[np.ndarray, str, np.ndarray]:
        image = Image.open(io.BytesIO(image_bytes))
        embedding = self._compute_embedding(image)

        if self.hash_length_override and self.hash_length_override < embedding.size:
            truncated = embedding[: self.hash_length_override]
        else:
            truncated = embedding

        mean = float(np.mean(truncated)) if truncated.size else 0.0
        std = float(np.std(truncated)) if truncated.size else 0.0
        if std > 0:
            normalized = (truncated - mean) / std
        else:
            normalized = truncated - mean
        bits = normalized >= 0
        hash_hex = _bits_to_hex(bits)
        return embedding.astype(np.float32), hash_hex, bits

    def match_against(
        self,
        query_hash: np.ndarray,
        query_embedding: np.ndarray,
        references: Iterable[Tuple[int, Optional[int], np.ndarray, np.ndarray]],
        *,
        max_results: int = 5,
        similarity_threshold: float = 0.75,
        max_hamming: Optional[int] = None,
    ) -> List[RecognitionResult]:
        query_bits = ensure_numpy_array(query_hash).astype(bool)
        query_vec = ensure_numpy_array(query_embedding).astype(np.float32)

        results: List[RecognitionResult] = []
        hash_length = query_bits.size

        for cat_id, ref_image_id, ref_hash_bits, ref_embedding in references:
            ref_bits = ensure_numpy_array(ref_hash_bits).astype(bool)
            ref_vec = ensure_numpy_array(ref_embedding).astype(np.float32)

            distance = hamming_distance(query_bits, ref_bits)
            if max_hamming is not None and distance > max_hamming:
                continue
            similarity = cosine_similarity(query_vec, ref_vec)
            matched = similarity >= similarity_threshold
            results.append(
                RecognitionResult(
                    cat_id=cat_id,
                    cat_name="",
                    similarity=similarity,
                    hamming_distance=distance,
                    reference_image_id=ref_image_id,
                    reference_hash_length=hash_length,
                    matched=matched,
                    metadata={
                        "hash_distance": float(distance),
                        "similarity": similarity,
                    },
                )
            )

        results.sort(key=lambda item: (-(item.similarity), item.hamming_distance))
        return results[:max_results]


def summarize_embeddings(embeddings: Iterable[np.ndarray]) -> Optional[np.ndarray]:
    vectors = [np.asarray(vec, dtype=np.float32) for vec in embeddings if vec is not None]
    if not vectors:
        return None
    centroid = np.mean(vectors, axis=0)
    norm = np.linalg.norm(centroid)
    if norm == 0:
        return centroid
    return centroid / norm


def aggregate_hashes(hashes: Iterable[np.ndarray]) -> Optional[str]:
    bit_arrays = [np.asarray(bits, dtype=bool) for bits in hashes if bits is not None]
    if not bit_arrays:
        return None
    max_len = max(bits.size for bits in bit_arrays)
    expanded = []
    for bits in bit_arrays:
        if bits.size < max_len:
            padded = np.zeros(max_len, dtype=bool)
            padded[: bits.size] = bits
            expanded.append(padded)
        else:
            expanded.append(bits[:max_len])
    votes = np.sum(expanded, axis=0)
    consensus = votes >= (len(expanded) / 2)
    return _bits_to_hex(consensus)


def embedding_to_blob(embedding: np.ndarray) -> bytes:
    return embedding.astype(np.float32).tobytes()


def blob_to_embedding(blob: bytes, length: Optional[int] = None) -> np.ndarray:
    if not blob:
        return np.array([], dtype=np.float32)
    array = np.frombuffer(blob, dtype=np.float32)
    if length is not None and array.size > length:
        return array[:length]
    return array


def ensure_numpy_array(value) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


