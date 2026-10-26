"""Shared, bounded product evidence for relevance and internal editorial hints."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

# ASCII boundaries deliberately allow Chinese next to an English product name,
# while avoiding substring accidents such as Cursor/precursor or Muse/museum.
_BRANDS = re.compile(
    r"(?<![a-z0-9])(?:chatgpt|openai|claude|anthropic|gemini|deepseek|copilot|codex|cursor|"
    r"qwen|minimax|kimi|seedance|seedream|viggle|openrouter|perplexity|workbuddy|"
    r"lovable|langchain|langsmith|krea|genspark|manus|comfyui)(?![a-z0-9])"
    r"|通义千问|千问|豆包|腾讯元宝|智谱清言|即梦|可灵|海螺AI", re.I,
)
_META_MUSE = re.compile(r"(?<![a-z0-9])(?:meta(?:['’]s)?\s+.{0,40}?muse|muse\s+spark)(?![a-z0-9])", re.I)
_VERSIONED_BRANDS = re.compile(
    r"(?<![a-z0-9])(?:qwen|minimax|kimi|seedance|seedream)[- ]?[mvh]?\d+(?:\.\d+)*(?:-[a-z0-9]+)*(?![a-z0-9])", re.I,
)
_HANDLES = {
    "viggleai": "viggle", "openrouter": "openrouter", "perplexity_ai": "perplexity",
    "workbuddy_ai": "workbuddy", "chatgpt": "chatgpt", "muse": "meta muse",
    "lovable_dev": "lovable", "krea_ai": "krea", "minimax_ai": "minimax",
}
_DOMAINS = {
    "viggle.ai": "viggle", "docs.viggle.ai": "viggle", "openrouter.ai": "openrouter",
    "perplexity.ai": "perplexity", "lovable.dev": "lovable", "docs.lovable.dev": "lovable",
    "langchain.com": "langchain", "krea.ai": "krea", "comfy.org": "comfyui",
}
# Verified account metadata supplements vague titles, never an arbitrary brand
# label supplied by an aggregator. Broad cloud/company accounts are excluded.
_WECHAT = {
    "qwen": {"千问app"}, "doubao": {"豆包"}, "hunyuan": {"腾讯元宝"},
    "kimi": {"kimi智能助手", "kimi"}, "minimax": {"minimax", "minimax稀宇科技"},
    "zhipu": {"智谱清言"}, "deepseek": {"deepseek", "深度求索"},
}
_ACTION = re.compile(
    r"(?<![a-z])(?:launch\w*|introduc\w*|releas\w*|roll\w*|add\w*|support\w*|"
    r"availab\w*|live|now|can|run\w*|generat\w*|use|using|built|build|"
    r"fix\w*|suspend\w*|disabl\w*|expos\w*|have)(?![a-z])"
    r"|上线|新增|推出|更新|发布|支持|接入|开放|可用|生成|完成|暂停|关闭|泄露|修复|接管|恢复|重置|调整|试试", re.I,
)
_CAPABILITY = re.compile(
    r"(?<![a-z])(?:apis?|sdks?|features?|dashboards?|workspaces?|integrations?|"
    r"subscriptions?|endpoints?|transcriptions?|captions?|object detection|pointing|chats?|conversations?|collaborat\w*|"
    r"editing|memory|connectors?|speech|audio|voice|3d|image editing|"
    r"local(?:ly)?|macs?|windows|desktop app|mobile app|new app)(?![a-z])"
    r"|功能|客户端|协作|共享屏幕|语音|视觉创作|全链路|工作流|多平台|电商经营|"
    r"本地运行|端侧运行|编辑|导出|上传|权限|隐私|对话|聊天|记忆|连接器|自动化|"
    r"模型切换|模型选择|模型接入|(?:接入|切换).{0,8}模型|桌面应用|移动应用|界面|订阅|会员|额度|限流|我的应用|专属应用", re.I,
)
_USAGE = re.compile(
    r"(?<![a-z])(?:how .{0,80}(?:use|built|build|works)|use cases?|customer stor\w*|tutorials?)(?![a-z])"
    r"|教程|手册|使用指南|上手|使用.{0,2}方法|讲解视频|解决方法|制作模式|应用场景|陪逛|解锁.{0,12}(?:玩法|逛法|用法)"
    r"|comfyui.{0,30}部署"
    r"|(?:用|使用|通过).{0,45}(?:做成|整理成|收录(?:进|到)|存(?:入|进)).{0,16}知识库"
    r"|(?:用|使用|部署).{0,45}(?:生成|制作|搭建|完成|实现|拍摄|拍了)|(?:agent|智能体).{0,24}(?:接管|完成|管理)", re.I,
)
_TECHNICAL = re.compile(
    r"(?<![a-z])(?:benchmarks?|eval(?:uation)?s?|inference|pretraining|training|"
    r"quantization|fine[- ]?tun\w*|throughput|tokenization|leaderboards?|latency)(?![a-z])"
    r"|评测|榜单|霸榜|国模第一|模型成本|基准测试|推理框架|推理优化|量化|预训练|微调|论文|吞吐|性能与成本", re.I,
)
_RELEASE = re.compile(r"launch\w*|introduc\w*|releas\w*|roll\w* out|now (?:on|live)|新增|上线|推出|接入|开放|功能更新", re.I)
_BUSINESS_CASE = re.compile(r"health coach|customer stor\w*|case stud\w*|应用案例|客户案例|应用场景", re.I)
_ADOPTION = re.compile(r"downloads?|active users?|使用量|调用量|下载量|活跃用户", re.I)
_PROMO = re.compile(r"抽奖|关注.{0,8}领|(?:领取|领|送|发放).{0,8}优惠券|充值.{0,10}(?:送|领)|节日快乐|新年快乐|中秋快乐|领红包")


def title_text(record: dict[str, Any]) -> str:
    # Do not use URL slugs or repeated promotional link footers as evidence.
    title = str(record.get("title") or "")
    title = re.split(r"more api access\s*[:：]", title, maxsplit=1, flags=re.I)[0]
    return re.sub(r"https?://\S+", "", title)


def product_identity(record: dict[str, Any], text: str) -> str | None:
    match = _BRANDS.search(text) or _VERSIONED_BRANDS.search(text)
    if match:
        return match[0].casefold()
    if _META_MUSE.search(text):
        return "meta muse"
    try:
        parsed = urlsplit(str(record.get("url") or record.get("primary_url") or ""))
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host in {"x.com", "twitter.com"}:
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 3 and parts[1] == "status":
            return _HANDLES.get(parts[0].casefold())
    if host in _DOMAINS:
        return _DOMAINS[host]
    if host == "mp.weixin.qq.com" and record.get("site_id") == "wechat_bridge" and record.get("account_verified") is True:
        account = re.sub(r"\s+", "", str(record.get("account_name") or "")).casefold()
        company = str(record.get("company_id") or "")
        if account in _WECHAT.get(company, set()):
            return company
    return None


def product_context(record: dict[str, Any]) -> dict[str, str] | None:
    """Require a known AI product and a concrete activity, not source trust alone."""
    text = title_text(record)
    identity = product_identity(record, text)
    if not identity or _PROMO.search(text):
        return None
    technical = _TECHNICAL.search(text)
    if technical and not (_RELEASE.search(text) and _CAPABILITY.search(text)) and not _BUSINESS_CASE.search(text):
        return {"identity": identity, "kind": "technical", "signal": "known_ai_product_technical_context"}
    if _USAGE.search(text) or (_ACTION.search(text) and _CAPABILITY.search(text)):
        return {"identity": identity, "kind": "product", "signal": "product_function_or_usage"}
    if _TECHNICAL.search(text):
        return {"identity": identity, "kind": "technical", "signal": "known_ai_product_technical_context"}
    if _ADOPTION.search(text):
        return {"identity": identity, "kind": "general", "signal": "known_ai_product_adoption"}
    return None
