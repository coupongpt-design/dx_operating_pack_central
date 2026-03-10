from dataclasses import dataclass, field, asdict
import os
import uuid
import logging
import numpy as np
from ..utils.common import decode_png_with_mask

LOGGER = logging.getLogger(__name__)


class ActionType:
    IMAGE_CLICK: str = "image_click"
    WAIT_FOR_IMAGE: str = "wait_for_image"
    IMAGE_MOVE: str = "image_move"
    IMAGE_DRAG: str = "image_drag"
    IMAGE_BRANCH: str = "image_branch"
    TARGET: str = "target"
    COMMENT: str = "comment"
    ACTION: str = "action"
    RUN_MACRO: str = "run_macro"

@dataclass
class StepData:
    # Backward compatibility: dict-like access
    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)
    id: str
    name: str
    type: str

    pre_delay_ms: int = 0
    
    # image matching
    png_bytes: bytes | None = None
    anchor_image_path: str | None = None   # user-provided template path (Option B)
    image_path: str | None = None          # archive/legacy template path compatibility
    relative_target_enabled: bool = False
    relative_target_png_bytes: bytes | None = None
    relative_target_image_path: str | None = None
    relative_search_mode: str = "px"
    relative_search_left: int = 0
    relative_search_top: int = 0
    relative_search_right: int = 0
    relative_search_bottom: int = 0
    relative_search_left_ratio: float = 0.0
    relative_search_top_ratio: float = 0.0
    relative_search_right_ratio: float = 0.0
    relative_search_bottom_ratio: float = 0.0
    find_all_targets: bool = False
    find_all_sub_steps: int = 0     # <<< '모두 찾기' 시 반복할 하위 스텝 개수
    hold_until_next: bool = False   # <<< 다음 이미지가 나타날 때까지 현재 동작 반복
    hold_timeout_ms: int = 5000
    hold_reclick_interval_ms: int = 500
    hold_reacquire_each_time: bool = False
    hold_release_consecutive: int = 1
    loop_until_hide: bool = False   # 이미지가 사라질 때까지 반복 클릭
    
    # --- Conditional Branching ---
    conditional_targets: list = field(default_factory=list)
    branch_on_fail_goto_id: str | None = None
    # Variable-branch mode support
    branch_mode: str = "image"            # "image" or "variable"
    branch_value_source: str = "variable" # "variable" or "ocr"
    branch_var: str | None = None
    branch_op: str = "=="
    branch_value: object | None = None
    branch_true_goto_id: str | None = None  # legacy
    branch_false_goto_id: str | None = None # legacy
    target_true_id: str | None = None
    target_false_id: str | None = None
    target_true_index: int | None = None
    target_false_index: int | None = None
    # OCR branch save option
    ocr_save_enabled: bool = False
    ocr_save_var: str | None = None
    threshold: float = 0.85
    min_confidence: float | None = None # [호환성] threshold와 유사한 역할
    timeout_ms: int = 5000
    poll_ms: int = 100
    jitter: int = 2
    pre_move_sleep_ms: int = 0
    press_duration_ms: int = 0
    post_click_sleep_ms: int = 0
    
    # --- Advanced Matching ---
    match_quality: str = "normal"
    top_k: int = 1
    match_color: bool = False
    color_match_tolerance: int = 10
    hq_color_bg_robust: bool = False
    alpha_mask_enable: bool = True
    auto_fg_mask_enable: bool = False
    auto_fg_mask_bg_percentile: float = 70.0
    auto_fg_mask_dynamic_scale: float = 0.6
    auto_fg_mask_min_distance: float = 12.0
    auto_fg_suggest_std_low: float = 18.0
    auto_fg_suggest_std_high: float = 42.0
    auto_fg_suggest_edge_low: float = 0.07
    auto_fg_suggest_edge_high: float = 0.20
    
    # --- Preprocessing ---
    pre_gray: bool = True
    pre_blur_ksize: int = 1
    pre_clahe: bool = False
    pre_edge: bool = False
    pre_sharpen: bool = False
    
    # --- Multi-scale / Rotation ---
    ms_min_scale: float = 0.9
    ms_max_scale: float = 1.1
    ms_step: float = 1.05
    rot_min_deg: float = -10.0
    rot_max_deg: float = 10.0
    rot_step_deg: float = 5.0
    max_rotations: int = 0
    max_scales: int = 0
    
    # --- Feature Matching (ORB) ---
    feat_fallback_enable: bool = False
    feat_nfeatures: int = 500
    feat_match_ratio: float = 0.75
    feat_ransac_reproj_thresh: float = 3.0
    
    # --- Performance / Cache ---
    budget_ms: int = 0
    tpl_cache_limit: int = 128
    
    # --- ROI ---
    search_roi_enabled: bool = False
    search_roi_left: int = 0
    search_roi_top: int = 0
    search_roi_width: int = 0
    search_roi_height: int = 0
    
    # --- Action ---
    image_action: str = "click"
    click_offset_x: int = 0
    click_offset_y: int = 0
    click_anchor: str = "center" # center, top-left, etc.
    
    # --- Non-Image Steps ---
    keyboard_mode: str = "text"
    mouse_mode: str = "click_point"
    screen_check_mode: str = "pixel_check"
    file_action_mode: str = "load_data_file"
    key_string: str | None = None
    key_times: int = 1
    hold_ms: int = 0
    comment: str = ""
    
    click_x: int | None = None
    click_y: int | None = None
    click_btn: str = "left"
    click_double: bool = False
    
    drag_from_x: int | None = None
    drag_from_y: int | None = None
    drag_to_x: int | None = None
    drag_to_y: int | None = None
    drag_duration_ms: int = 0
    drag_path: list | None = None # [(x,y,ts), ...]
    
    scroll_dx: int = 0
    scroll_dy: int = 0
    scroll_times: int = 1
    scroll_interval_ms: int = 0
    wait_ms: int = 0
    
    pixel_x: int | None = None
    pixel_y: int | None = None
    pixel_color_hex: str | None = None
    pixel_color_tolerance: int = 0
    pixel_success_goto_id: str | None = None
    
    # --- Loop Control ---
    loop_count: int = 1
    start_loop_id: str | None = None

    # --- Conditional Logic (Jump/Branch) ---
    condition_var: str | None = None
    condition_value: object | None = None
    condition_operator: str = "=="
    jump_to_index: int | None = None   # legacy
    jump_to_step_id: str | None = None # legacy

    # --- Sub-script (run macro) ---
    target_macro_path: str = ""
    
    # --- Image Compare ---
    image_a_path: str | None = None
    image_b_path: str | None = None
    compare_mode: str = "mse" # mse, ssim, hash
    compare_threshold: float = 0.0
    compare_roi_x: int = 0
    compare_roi_y: int = 0
    compare_roi_w: int = 0
    compare_roi_h: int = 0
    
    # --- Screenshot ROI ---
    screenshot_roi_x: int = 0
    screenshot_roi_y: int = 0
    screenshot_roi_w: int = 0
    screenshot_roi_h: int = 0
    screenshot_save_path: str | None = None
    
    # --- OCR Check ---
    ocr_roi_x: int = 0
    ocr_roi_y: int = 0
    ocr_roi_w: int = 0
    ocr_roi_h: int = 0
    ocr_expected_text: str | None = None
    ocr_lang: str = "eng"
    ocr_preprocess_mode: str = "none" # none, thresh, blur
    ocr_target_height: int = 0 # 0=auto
    ocr_whitelist: str | None = None
    ocr_use_dynamic_data: bool = False      # 'Expected Text' 대신 로드한 데이터 사용 여부
    ocr_store_var: str | None = None
    ocr_scale: float = 2.0
    ocr_invert: bool = False
    
    # 'on_match_goto_id'와 'branch_on_fail_goto_id'는 compare_images와 공유
    on_match_goto_id: str | None = None
    
    # --- [신규] Data Loading ---
    data_file_path: str | None = None       # load_data_file 스텝에서 사용할 파일 경로

    # --- Legacy Compatibility (Auto-migration) ---
    click_button: str | None = None
    repeat_count: int | None = None
    screenshot_filepath: str | None = None

    def __post_init__(self):
        mode = str(getattr(self, "relative_search_mode", "px") or "px").strip().lower()
        self.relative_search_mode = mode if mode in {"px", "ratio"} else "px"
        if self.click_button is not None:
            self.click_btn = self.click_button
        if self.repeat_count is not None:
            self.loop_count = self.repeat_count
        if self.screenshot_filepath is not None:
            self.screenshot_save_path = self.screenshot_filepath
        if not self.anchor_image_path and self.image_path:
            self.anchor_image_path = self.image_path
        # --- Target mapping compatibility ---
        # normalize jump/branch target IDs to target_true_id/target_false_id
        if self.target_true_id is None:
            if self.jump_to_step_id is not None:
                self.target_true_id = self.jump_to_step_id
            elif self.branch_true_goto_id is not None:
                self.target_true_id = self.branch_true_goto_id
            elif hasattr(self, "target_true"):
                try:
                    self.target_true_id = getattr(self, "target_true")
                except Exception as e:
                    LOGGER.debug("Failed to read legacy 'target_true' attribute: %s", e)
        if self.target_false_id is None:
            if self.branch_false_goto_id is not None:
                self.target_false_id = self.branch_false_goto_id
            elif hasattr(self, "target_false"):
                try:
                    self.target_false_id = getattr(self, "target_false")
                except Exception as e:
                    LOGGER.debug("Failed to read legacy 'target_false' attribute: %s", e)
        if self.target_true_index is None and self.jump_to_index is not None:
            self.target_true_index = self.jump_to_index

    # Runtime cache
    _tpl_bgr: np.ndarray | None = field(default=None, repr=False)
    _tpl_mask: np.ndarray | None = field(default=None, repr=False)
    _tpl_cache: dict = field(default_factory=dict, repr=False)
    _last_match_xy: tuple | None = field(default=None, repr=False)

    def ensure_tpl(self) -> np.ndarray | None:
        if self._tpl_bgr is not None:
            return self._tpl_bgr
        raw = self.png_bytes
        if not raw:
            path = str(self.anchor_image_path or self.image_path or "").strip()
            if path:
                try:
                    resolved = os.path.expandvars(os.path.expanduser(path))
                    if not os.path.isabs(resolved):
                        resolved = os.path.abspath(resolved)
                    if os.path.exists(resolved):
                        with open(resolved, "rb") as f:
                            raw = f.read()
                        self.png_bytes = raw
                except Exception as e:
                    LOGGER.debug("Failed to load template image from path '%s': %s", path, e)
        if not raw:
            return None
        tpl_bgr, tpl_mask = decode_png_with_mask(raw)
        self._tpl_bgr = tpl_bgr
        self._tpl_mask = tpl_mask
        return self._tpl_bgr

    def to_serializable(self) -> dict:
        d = asdict(self)
        d.pop('_tpl_cache', None)
        d.pop("_tpl_bgr", None)
        d.pop("_tpl_mask", None)
        d.pop("_last_match_xy", None)
        
        if self.type == 'image_branch':
            targets_serial = []
            for target in self.conditional_targets:
                t_copy = target.copy()
                t_copy['image_path'] = f"images/{t_copy['id']}.png"
                t_copy.pop('png_bytes', None)
                targets_serial.append(t_copy)
            d['conditional_targets'] = targets_serial
            
        if self.type in {"image_click", "wait_for_image"} and self.png_bytes:
            d['image_path'] = f"images/{self.id}.png"
            d.pop('png_bytes', None)
        if self.type in {"image_click", "wait_for_image"} and self.relative_target_png_bytes:
            d['relative_target_image_path'] = f"images/{self.id}_relative_target.png"
            d.pop('relative_target_png_bytes', None)
            
        # Remove defaults to save space (optional optimization)
        return d

    # Alias for callers expecting to_dict
    def to_dict(self) -> dict:
        return self.to_serializable()

@dataclass
class RepeatConfig:
    repeat_count: int = 1       # 0 = infinite
    repeat_cooldown_ms: int = 500 # cooldown between loops
    stop_on_fail: bool = True   # stop all on first step failure
    max_duration_ms: int = 0    # 0 = no limit

    def to_json(self) -> dict:
        return {
            "repeat_count": int(self.repeat_count),
            "repeat_cooldown_ms": int(self.repeat_cooldown_ms),
            "stop_on_fail": bool(self.stop_on_fail),
            "max_duration_ms": int(self.max_duration_ms),
        }

    @staticmethod
    def from_json(d: dict) -> "RepeatConfig":
        rc = RepeatConfig()
        if not isinstance(d, dict):
            return rc
        rc.repeat_count = int(d.get("repeat_count", rc.repeat_count))
        rc.repeat_cooldown_ms = int(d.get("repeat_cooldown_ms", rc.repeat_cooldown_ms))
        rc.stop_on_fail = bool(d.get("stop_on_fail", rc.stop_on_fail))
        rc.max_duration_ms = int(d.get("max_duration_ms", rc.max_duration_ms))
        return rc

@dataclass
class TriggerData:
    id: str
    name: str
    enabled: bool = True
    
    # Condition: We wrap a StepData object.
    # Usually type='image_click' for image triggers.
    condition_step: StepData = field(default_factory=lambda: StepData(id=str(uuid.uuid4())[:8], name="Condition", type="image_click"))
    
    # Action
    action_type: str = "run_macro" # run_macro, stop, notification
    action_value: str = "" # macro file path or message
    
    # Control
    cooldown_ms: int = 5000
    last_fired: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d['condition_step'] = self.condition_step.to_serializable()
        return d

    @staticmethod
    def from_dict(d: dict) -> "TriggerData":
        # Handle legacy or new format
        if 'condition_step' in d:
            step_dict = d.pop('condition_step')
            step = StepData(**step_dict)
            # Ensure tpl if needed (handled by loader usually, but good to be safe)
            t = TriggerData(**d)
            t.condition_step = step
            return t
        else:
            # Migration from old flat format (if any exist in wild, though we just made it)
            t = TriggerData(
                id=d.get('id', str(uuid.uuid4())[:8]),
                name=d.get('name', 'Trigger'),
                enabled=d.get('enabled', True),
                action_type=d.get('action_type', 'run_macro'),
                action_value=d.get('action_value', ''),
                cooldown_ms=d.get('cooldown_ms', 5000),
                last_fired=d.get('last_fired', 0.0)
            )
            # Create a step from flat fields
            s = StepData(id=str(uuid.uuid4())[:8], name="Condition", type="image_click")
            s.threshold = d.get('threshold', 0.9)
            s.search_roi_enabled = d.get('roi_enabled', False)
            s.search_roi_left = d.get('roi_left', 0)
            s.search_roi_top = d.get('roi_top', 0)
            s.search_roi_width = d.get('roi_width', 0)
            s.search_roi_height = d.get('roi_height', 0)
            # Image handling would need external help (loading bytes)
            # We assume migration logic handles bytes loading if needed.
            t.condition_step = s
            return t
