import json
import zipfile
import logging
from dataclasses import fields
from ..core.models import StepData, RepeatConfig

LOGGER = logging.getLogger(__name__)

class MacroIO:
    @staticmethod
    def save_macro(path: str, steps: list[StepData], repeat_config: RepeatConfig):
        with zipfile.ZipFile(path, 'w') as z:
            # Scenario JSON
            scen_data = {
                "version": "2.0",
                "repeat": repeat_config.to_json(),
                "steps": [s.to_serializable() for s in steps]
            }
            z.writestr("scenario.json", json.dumps(scen_data, indent=2))
            
            for s in steps:
                if s.type == 'image_click' and s.png_bytes:
                    z.writestr(f"images/{s.id}.png", s.png_bytes)
                if s.type == 'image_branch':
                    for t in s.conditional_targets:
                        if t.get('png_bytes'):
                            z.writestr(f"images/{t['id']}.png", t['png_bytes'])

    @staticmethod
    def load_macro(path: str) -> tuple[list[StepData], RepeatConfig]:
        with zipfile.ZipFile(path, "r") as z:
            scen = json.loads(z.read("scenario.json").decode("utf-8"))
            rep = scen.get("repeat", {})
            rc = RepeatConfig.from_json(rep)
            
            steps_data = scen.get("steps", [])
            new_steps = []
            
            # [Safety] Get valid fields for StepData
            valid_fields = {f.name for f in fields(StepData)}
            
            for d in steps_data:
                # Filter unknown fields to prevent TypeError
                ctor_args = {k: v for k, v in d.items() if k in valid_fields}
                s = StepData(**ctor_args)
                # Load image if needed
                if s.type == 'image_click' and d.get('image_path'):
                    try:
                        s.png_bytes = z.read(d['image_path'])
                    except KeyError as e:
                        LOGGER.warning("Missing image entry in macro archive: %s (%s)", d.get("image_path"), e)
                if s.type == 'image_branch':
                    new_targets = []
                    for t in s.conditional_targets:
                        if t.get('image_path'):
                            try:
                                t['png_bytes'] = z.read(t['image_path'])
                            except KeyError as e:
                                LOGGER.warning("Missing branch target image in macro archive: %s (%s)", t.get("image_path"), e)
                        new_targets.append(t)
                    s.conditional_targets = new_targets
                
                if s.type == 'image_click':
                    s.ensure_tpl()
                new_steps.append(s)
            
            return new_steps, rc
