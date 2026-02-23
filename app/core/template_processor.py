import re
from collections.abc import Mapping


class TemplateProcessor:
    """Shared placeholder replacement for action runners."""

    _TOKEN_PATTERN = re.compile(r"\{\{\s*([A-Za-z_]\w*)\s*\}\}|\{([A-Za-z_]\w*)\}")

    @classmethod
    def render(cls, text: str, values: Mapping[str, object] | None = None) -> str:
        values = values or {}
        source = str(text or "")
        lowered_values: dict[str, object] = {}
        for key, value in values.items():
            norm_key = str(key)
            lowered_values.setdefault(norm_key.lower(), value)

        def _replace(match: re.Match[str]) -> str:
            key = match.group(1) or match.group(2)
            if key in values:
                value = values.get(key)
                return "" if value is None else str(value)
            lowered_key = str(key).lower()
            if lowered_key in lowered_values:
                value = lowered_values.get(lowered_key)
                return "" if value is None else str(value)
            return match.group(0)

        return cls._TOKEN_PATTERN.sub(_replace, source)

    @classmethod
    def has_unresolved_placeholder(cls, text: str) -> bool:
        return bool(cls._TOKEN_PATTERN.search(str(text or "")))
