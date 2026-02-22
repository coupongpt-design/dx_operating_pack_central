import json
import logging
import posixpath
import zipfile
from dataclasses import fields

from ..core.models import RepeatConfig, StepData

LOGGER = logging.getLogger(__name__)

_ARCHIVE_JSON_PRIMARY = "template.json"
_ARCHIVE_JSON_LEGACY = "scenario.json"
_ASSET_PREFIX_NEW = "assets/"
_ASSET_PREFIX_LEGACY = "images/"
_ALLOWED_ASSET_PREFIXES = (_ASSET_PREFIX_NEW, _ASSET_PREFIX_LEGACY)


def _normalize_archive_member(member: str) -> str | None:
    raw = str(member or "").strip().replace("\\", "/")
    if not raw:
        return None
    if raw.startswith("/") or raw.startswith("../") or raw.startswith("..\\"):
        return None
    if ":" in raw:
        # Windows drive-like path in archive references is not allowed.
        return None
    norm = posixpath.normpath(raw)
    if norm in {".", ""}:
        return None
    if norm.startswith("../") or norm == "..":
        return None
    return norm


def _resolve_safe_asset_member(name: str, members: set[str]) -> str | None:
    norm = _normalize_archive_member(name)
    if not norm:
        return None
    if not any(norm.startswith(prefix) for prefix in _ALLOWED_ASSET_PREFIXES):
        return None
    if norm not in members:
        return None
    return norm


def _read_payload_from_archive(z: zipfile.ZipFile, member_set: set[str]) -> dict:
    json_member = _ARCHIVE_JSON_PRIMARY if _ARCHIVE_JSON_PRIMARY in member_set else _ARCHIVE_JSON_LEGACY
    return json.loads(z.read(json_member).decode("utf-8"))


class MacroIO:
    @staticmethod
    def save_macro(path: str, steps: list[StepData], repeat_config: RepeatConfig, meta: dict | None = None):
        # Use Option C package structure by default:
        #  - template.json
        #  - assets/<id>.png
        steps_serialized = []
        for s in steps:
            item = s.to_serializable()
            if s.type in {"image_click", "wait_for_image"} and s.png_bytes:
                item["image_path"] = f"{_ASSET_PREFIX_NEW}{s.id}.png"
            if s.type == "image_branch":
                targets = []
                for t in item.get("conditional_targets", []) or []:
                    t_copy = dict(t)
                    if t_copy.get("id"):
                        t_copy["image_path"] = f"{_ASSET_PREFIX_NEW}{t_copy['id']}.png"
                    targets.append(t_copy)
                item["conditional_targets"] = targets
            steps_serialized.append(item)

        payload = {
            "schema_version": 1,
            "version": "3.0",
            "repeat": repeat_config.to_json(),
            "steps": steps_serialized,
        }
        if isinstance(meta, dict):
            payload["meta"] = dict(meta)

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(_ARCHIVE_JSON_PRIMARY, json.dumps(payload, indent=2, ensure_ascii=False))

            for s in steps:
                if s.type in {"image_click", "wait_for_image"} and s.png_bytes:
                    z.writestr(f"{_ASSET_PREFIX_NEW}{s.id}.png", s.png_bytes)
                if s.type == "image_branch":
                    for t in s.conditional_targets:
                        png_bytes = t.get("png_bytes")
                        tid = t.get("id")
                        if tid and png_bytes:
                            z.writestr(f"{_ASSET_PREFIX_NEW}{tid}.png", png_bytes)

    @staticmethod
    def load_macro_payload(path: str) -> dict:
        with zipfile.ZipFile(path, "r") as z:
            member_set = set(z.namelist())
            return _read_payload_from_archive(z, member_set)

    @staticmethod
    def load_macro(path: str) -> tuple[list[StepData], RepeatConfig]:
        with zipfile.ZipFile(path, "r") as z:
            member_set = set(z.namelist())
            scen = _read_payload_from_archive(z, member_set)
            rep = scen.get("repeat", {})
            rc = RepeatConfig.from_json(rep)

            steps_data = scen.get("steps", [])
            new_steps = []
            valid_fields = {f.name for f in fields(StepData)}

            for d in steps_data:
                ctor_args = {k: v for k, v in d.items() if k in valid_fields}
                s = StepData(**ctor_args)

                if s.type in {"image_click", "wait_for_image"} and d.get("image_path"):
                    asset_name = _resolve_safe_asset_member(str(d.get("image_path", "")), member_set)
                    if asset_name:
                        try:
                            s.png_bytes = z.read(asset_name)
                        except KeyError as e:
                            LOGGER.warning("Missing image entry in macro archive: %s (%s)", d.get("image_path"), e)
                    else:
                        LOGGER.warning("Blocked unsafe image_path in macro archive: %s", d.get("image_path"))

                if s.type == "image_branch":
                    new_targets = []
                    for t in s.conditional_targets:
                        t_copy = dict(t)
                        if t_copy.get("image_path"):
                            asset_name = _resolve_safe_asset_member(str(t_copy.get("image_path", "")), member_set)
                            if asset_name:
                                try:
                                    t_copy["png_bytes"] = z.read(asset_name)
                                except KeyError as e:
                                    LOGGER.warning(
                                        "Missing branch target image in macro archive: %s (%s)",
                                        t_copy.get("image_path"),
                                        e,
                                    )
                            else:
                                LOGGER.warning(
                                    "Blocked unsafe branch image_path in macro archive: %s",
                                    t_copy.get("image_path"),
                                )
                        new_targets.append(t_copy)
                    s.conditional_targets = new_targets

                if s.type in {"image_click", "wait_for_image"}:
                    s.ensure_tpl()
                new_steps.append(s)

            return new_steps, rc
