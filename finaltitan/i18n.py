"""UI languages: string catalogs per language and language-neutral messages. No Streamlit imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from .catalog import DATA_DIR

LANGS = ("en", "de")
DEFAULT = "en"
NAMES = {"en": "English", "de": "Deutsch"}
I18N_DIR = DATA_DIR / "i18n"


@dataclass(frozen=True)
class Msg:
    """A text to be rendered later in the viewer's language. Params may be Msgs or lists of Msgs."""
    key: str
    params: dict[str, Any] = field(default_factory=dict)


def msg(key: str, **params: Any) -> Msg:
    return Msg(key, params)


@lru_cache(maxsize=4)
def _load(lang: str, mtime: float) -> dict[str, str]:
    with open(I18N_DIR / f"{lang}.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def strings(lang: str) -> dict[str, str]:
    path = I18N_DIR / f"{lang}.yaml"
    return _load(lang, path.stat().st_mtime) if path.exists() else {}


def norm(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT


def pick_lang(locale: str | None) -> str:
    """'de-AT' -> 'de'; anything unknown falls back to English."""
    return norm((locale or "").replace("_", "-").split("-")[0].lower())


class _Ctx(dict):
    def __missing__(self, key: str) -> str:
        return ""


def t(key: str, lang: str, **params: Any) -> str:
    """The text for key in lang, falling back to English and then to the key itself."""
    text = strings(norm(lang)).get(key)
    if text is None:
        text = strings(DEFAULT).get(key, key)
    if not params:
        return text
    ctx = _Ctx({k: _value(v, lang) for k, v in params.items()})
    return text.format_map(ctx)


def _value(value: Any, lang: str) -> Any:
    if isinstance(value, Msg):
        return render(value, lang)
    if isinstance(value, list):
        return t("join.list", lang).join(str(_value(v, lang)) for v in value)
    return value


def render(m: Msg | str, lang: str) -> str:
    return m if isinstance(m, str) else t(m.key, lang, **m.params)


def text(value: Any, lang: str) -> str:
    """A {lang: text} mapping from a data file, or a plain string, in lang (English fallback)."""
    if isinstance(value, dict):
        return str(value.get(norm(lang), value.get(DEFAULT, "")))
    return "" if value is None else str(value)
