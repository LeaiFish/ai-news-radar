"""Internal editorial hints: technical evidence informs, but does not imply, a product launch.

These fields stay out of the public reader projection. Source authority and AI
relevance are independent of the product/technical priority used for selection.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

try:
    from scripts.product_context import product_context
except ModuleNotFoundError:
    from product_context import product_context

_PRODUCT = re.compile(
    r"(?:\b(?:launch\w*|introduc\w*|new|release\w*|roll\w* out)\b.{0,80}"
    r"\b(?:app|dashboard|feature|tool|workspace|integration|subscription|api)\b)"
    r"|\b(?:use case|health coach|customer story|how .{0,60}built)\b"
    r"|新功能|功能更新|客户端|产品发布|应用场景|使用体验|陪逛|协作功能", re.I,
)
_TECHNICAL = re.compile(
    r"\b(?:benchmark\w*|eval(?:uation)?s?|inference|pretraining|fine[- ]?tun\w*|"
    r"quantization|tokenization|throughput|context engineering|training|arxiv)\b"
    r"|评测|榜单|基准测试|推理框架|推理优化|量化|预训练|微调|论文|吞吐|性能与成本", re.I,
)


def editorial_tags(row: dict[str, Any]) -> list[str]:
    source = str(row.get("source") or "").casefold()
    title = str(row.get("title") or "")
    if source == "hugging face open-r1 commits":
        return ["model_technology"]  # Repository maintenance is not a product launch.
    url = str(row.get("url") or row.get("primary_url") or "")
    try:
        parsed = urlsplit(url)
    except ValueError:
        parsed = urlsplit("")
    host = (parsed.hostname or "").removeprefix("www.")
    handle = parsed.path.strip("/").split("/")[0].casefold() if host in {"x.com", "twitter.com"} else ""
    if handle in {"arena", "artificialanlys"} or host == "artificialanalysis.ai" or any(
        name in source for name in ("artificial analysis", "x：arena")
    ):
        return ["model_evaluation"]
    if host in {"vllm.ai", "blog.vllm.ai", "lmsys.org", "pytorch.org"} or any(name in source for name in ("vllm", "lmsys", "pytorch")):
        return ["model_technology"]
    context = product_context(row)
    if context and context["kind"] == "product":
        return ["product_update"]
    if context and context["kind"] == "technical":
        return ["technical_research"]
    if _PRODUCT.search(title):
        return ["product_update"]
    if row.get("aihot_category") == "paper" or "anthropic.com/research/" in url or "alignment.openai.com/" in url:
        return ["technical_research"]
    if _TECHNICAL.search(title) or any(name in source for name in ("meta engineering", "marktechpost research")):
        return ["technical_research"]
    return []


def editorial_focus(row: dict[str, Any]) -> str:
    tags = editorial_tags(row)
    if "product_update" in tags:
        return "product"
    return "technical" if tags else "general"


def add_editorial_focus(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "editorial_focus": editorial_focus(row), "editorial_tags": editorial_tags(row)}


def story_editorial_focus(story: dict[str, Any]) -> str:
    refs = story.get("items") or story.get("sources") or []
    focuses = [editorial_focus(ref) for ref in refs if isinstance(ref, dict)]
    if not focuses:
        return editorial_focus(story)
    if "product" in focuses:
        return "product"
    return "technical" if all(focus == "technical" for focus in focuses) else "general"
