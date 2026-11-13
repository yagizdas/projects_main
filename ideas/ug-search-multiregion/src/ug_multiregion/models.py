"""MLLM adapters. The mock is deterministic and requires no GPU."""

from __future__ import annotations

import hashlib
from typing import Protocol
from PIL import Image, ImageStat

from .official import entropy_hook


class VisionLanguageModel(Protocol):
    def entropy(self, images: list[Image.Image], question: str) -> float: ...
    def answer(self, images: list[Image.Image], question: str, choices: list[str] | None = None) -> str: ...


class MockModel:
    """Stable CPU stand-in whose score depends on all supplied visual regions."""
    def entropy(self, images: list[Image.Image], question: str) -> float:
        if not images:
            return 10.0
        information = sum(ImageStat.Stat(image.convert("L").resize((8, 8))).var[0] for image in images)
        return round(1 / (1 + information / 1000) + 0.02 / len(images), 8)

    def answer(self, images: list[Image.Image], question: str, choices: list[str] | None = None) -> str:
        if choices:
            digest = hashlib.sha256((question + f"/{len(images)}").encode()).digest()
            return choices[int.from_bytes(digest[:2], "big") % len(choices)]
        return "mock"


class TransformersModel:
    """Generic Hugging Face image-text-to-text adapter using generated-token entropy."""
    def __init__(self, model_id: str, max_new_tokens: int = 128):
        try:
            import torch
            import torch.nn.functional as functional
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as exc:
            raise RuntimeError("Install the 'gpu' extra to use a real model") from exc
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id, torch_dtype="auto", device_map="auto", trust_remote_code=True).eval()
        self.max_new_tokens = max_new_tokens
        self.cur_entropy: list[float] = []
        self._entropy_hook = entropy_hook(torch, functional).__get__(self)

    def _inputs(self, images: list[Image.Image], question: str):
        content = [{"type": "image"} for _ in images] + [{"type": "text", "text": question}]
        prompt = self.processor.apply_chat_template(
            [{"role": "user", "content": content}], add_generation_prompt=True, tokenize=False)
        values = self.processor(text=[prompt], images=images, return_tensors="pt")
        return {key: value.to(self.model.device) for key, value in values.items()}

    def _generate(self, images: list[Image.Image], question: str, scores: bool = False):
        inputs = self._inputs(images, question)
        with self.torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens,
                                         do_sample=False, return_dict_in_generate=True,
                                         output_scores=scores)
        return inputs, output

    def entropy(self, images: list[Image.Image], question: str) -> float:
        self.cur_entropy = []
        handle = self.model.lm_head.register_forward_hook(self._entropy_hook)
        try:
            self._generate(images, question)
        finally:
            handle.remove()
        return sum(self.cur_entropy) / len(self.cur_entropy) if self.cur_entropy else float("inf")

    def answer(self, images: list[Image.Image], question: str, choices: list[str] | None = None) -> str:
        if choices:
            question += "\nAnswer with exactly one of: " + ", ".join(choices)
        inputs, output = self._generate(images, question)
        length = inputs["input_ids"].shape[1]
        return self.processor.batch_decode(output.sequences[:, length:], skip_special_tokens=True)[0].strip()


def make_model(model_id: str, dry_run: bool, max_new_tokens: int = 128) -> VisionLanguageModel:
    return MockModel() if dry_run else TransformersModel(model_id, max_new_tokens)
