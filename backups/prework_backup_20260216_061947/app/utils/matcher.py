import cv2
import numpy as np
import time
import logging
from ..core.models import StepData

LOGGER = logging.getLogger(__name__)

class MatchResult:
    """Template matching outcome with optional timing info."""
    def __init__(
        self,
        ok: bool,
        x: int | None = None,
        y: int | None = None,
        score: float = 0.0,
        w: int = 0,
        h: int = 0,
        stage: str = "single",
        scale: float = 1.0,
        angle: float = 0.0,
        timing: dict | None = None,
    ) -> None:
        self.ok = ok
        self.x = x
        self.y = y
        self.score = score
        self.w = w
        self.h = h
        self.stage = stage
        self.scale = scale
        self.angle = angle
        self.timing = timing or {}

def _apply_preprocess(img_bgr: np.ndarray, step: StepData, overrides: dict | None = None) -> np.ndarray:
    """Apply lightweight preprocessing and return contiguous array."""
    def _get(name: str, default):
        if overrides and name in overrides:
            return overrides[name]
        return getattr(step, name, default)

    match_color = bool(_get("match_color", False))
    force_gray = bool(overrides.get("force_gray", False)) if overrides else False
    try:
        img = img_bgr
        needs_gray = force_gray or ((not match_color) and bool(_get("pre_gray", False) or _get("pre_edge", False) or _get("pre_clahe", False)))
        
        if needs_gray and len(getattr(img, "shape", ())) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if _get("pre_clahe", False) and len(getattr(img, "shape", ())) == 2:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = clahe.apply(img)
            
        ksize = int(_get("pre_blur_ksize", 1))
        if ksize > 1:
            if ksize % 2 == 0: ksize += 1
            img = cv2.GaussianBlur(img, (ksize, ksize), 0)
            
        if _get("pre_edge", False):
            if len(getattr(img, "shape", ())) == 3: # Color Canny
                # Convert to gray for Canny, or apply per channel? Usually Canny is on gray.
                # If we are here, needs_gray was False, so match_color is True.
                # Canny on color is weird. Let's skip or do gray temp.
                # Original code: if len... == 3: img = cv2.Canny(img, 80, 160) -> This works in OpenCV (uses intensity)
                try:
                    img = cv2.Canny(img, 80, 160)
                except Exception as e:
                    LOGGER.debug("Color Canny preprocessing skipped (non-fatal): %s", e)
            elif len(getattr(img, "shape", ())) == 2:
                try:
                    img = cv2.Canny(img, 80, 160)
                except Exception as e:
                    LOGGER.debug("Grayscale Canny preprocessing skipped (non-fatal): %s", e)
                    
        if _get("pre_sharpen", False):
            k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
            img = cv2.filter2D(img, -1, k)
            
        return np.ascontiguousarray(img)
    except Exception:
        import traceback
        traceback.print_exc()
        return np.ascontiguousarray(img_bgr)

def _resize_keep(template, scale):
    nh, nw = max(1, int(template.shape[0]*scale)), max(1, int(template.shape[1]*scale))
    if nh < 2 or nw < 2:
        return None
    return cv2.resize(template, (nw, nh), interpolation=cv2.INTER_LINEAR)

def _rotate_template(tpl, angle_deg):
    h, w = tpl.shape[:2]
    center = (w/2.0, h/2.0)
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    rot = cv2.warpAffine(tpl, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return rot

def match_template_with_color(img_like: np.ndarray, tpl_like: np.ndarray, step: StepData, mask: np.ndarray | None = None) -> np.ndarray:
    use_color = bool(getattr(step, "match_color", False))
    if (not use_color or len(getattr(img_like, "shape", ())) < 3):
        if mask is not None:
            return cv2.matchTemplate(img_like, tpl_like, cv2.TM_CCOEFF_NORMED, mask=mask)
        return cv2.matchTemplate(img_like, tpl_like, cv2.TM_CCOEFF_NORMED)
    
    res = None
    for ch in range(3):
        channel_res = cv2.matchTemplate(img_like[:, :, ch], tpl_like[:, :, ch], cv2.TM_CCOEFF_NORMED)
        if res is None:
            res = channel_res
        else:
            res = np.minimum(res, channel_res)
    return res

def _extract_topk(resmap, k=1, tpl_w=0, tpl_h=0):
    cands = []
    res = resmap.copy()
    for _ in range(max(1, int(k))):
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        cands.append((maxv, maxloc[0], maxloc[1]))
        x0, y0 = maxloc[0], maxloc[1]
        x1 = max(0, x0 - tpl_w//3)
        y1 = max(0, y0 - tpl_h//3)
        x2 = min(res.shape[1]-1, x0 + tpl_w//3)
        y2 = min(res.shape[0]-1, y0 + tpl_h//3)
        res[y1:y2+1, x1:x2+1] = -1.0
    return cands

class Matcher:
    def __init__(self):
        pass
    
    def _color_gate_enabled(self, step: StepData) -> bool:
        return bool(getattr(step, "match_color", False)) and int(getattr(step, "color_match_tolerance", 0) or 0) > 0

    def _color_gate_passed(self, frame_like: np.ndarray, tpl_like: np.ndarray | None, x: int, y: int, step: StepData) -> bool:
        if not self._color_gate_enabled(step):
            return True
        if tpl_like is None:
            return False
        h, w = tpl_like.shape[:2]
        if h <= 0 or w <= 0:
            return False
        if frame_like is None or frame_like.size == 0:
            return False
        if y < 0 or x < 0 or y + h > frame_like.shape[0] or x + w > frame_like.shape[1]:
            return False
        try:
            roi = frame_like[y:y + h, x:x + w]
            if roi.shape != tpl_like.shape:
                if len(roi.shape) == len(tpl_like.shape) == 3:
                    min_c = min(roi.shape[2], tpl_like.shape[2])
                    roi = roi[:, :, :min_c]
                    tpl_like = tpl_like[:, :, :min_c]
                else:
                    return False
            diff = cv2.absdiff(roi, tpl_like)
            mean_diff = float(np.mean(diff))
            tolerance = max(0, int(getattr(step, "color_match_tolerance", 0) or 0))
            return mean_diff <= tolerance
        except Exception:
            # This can happen if ROI is out of bounds or image types mismatch
            return False
    
    def _pp_key(self, step, overrides: dict | None = None):
        def _get(name: str, default):
            if overrides and name in overrides:
                return overrides[name]
            return getattr(step, name, default)

        force_gray = bool(overrides.get("force_gray", False)) if overrides else False
        return (
            bool(_get("pre_gray", True)),
            int(_get("pre_blur_ksize", 1)),
            bool(_get("pre_clahe", False)),
            bool(_get("pre_edge", False)),
            bool(_get("pre_sharpen", False)),
            bool(_get("match_color", False)),
            force_gray,
        )

    def _get_pp_tpl(self, tpl_bgr, step, overrides: dict | None = None):
        cache = getattr(step, "_tpl_cache", None)
        if cache is None:
            step._tpl_cache = cache = {}
        key = ("pp", self._pp_key(step, overrides))
        if key in cache:
            val = cache.pop(key)
            cache[key] = val
            return val
        pp = _apply_preprocess(tpl_bgr, step, overrides)
        cache[key] = pp
        limit = int(getattr(step, "tpl_cache_limit", 128) or 0)
        if limit > 0:
            while len(cache) > limit:
                try:
                    first_key = next(iter(cache))
                    cache.pop(first_key, None)
                except Exception:
                    break
        return pp

    def _get_scale_tpl(self, tpl_pp, step, sc, overrides: dict | None = None):
        cache = getattr(step, "_tpl_cache", None)
        if cache is None:
            step._tpl_cache = cache = {}
        key = ("scale", self._pp_key(step, overrides), float(sc))
        if key in cache:
            val = cache.pop(key)
            cache[key] = val
            return val
        tpl_s = _resize_keep(tpl_pp, float(sc))
        cache[key] = tpl_s
        limit = int(getattr(step, "tpl_cache_limit", 128) or 0)
        if limit > 0:
            while len(cache) > limit:
                try:
                    first_key = next(iter(cache))
                    cache.pop(first_key, None)
                except Exception:
                    break
        return tpl_s

    def _get_rot_tpl(self, tpl_pp, step, ang, overrides: dict | None = None, extra_key=None):
        cache = getattr(step, "_tpl_cache", None)
        if cache is None:
            step._tpl_cache = cache = {}
        key = ("rot", self._pp_key(step, overrides), float(ang))
        if extra_key is not None:
            key = ("rot", self._pp_key(step, overrides), extra_key, float(ang))
        if key in cache:
            val = cache.pop(key)
            cache[key] = val
            return val
        rot = _rotate_template(tpl_pp, float(ang))
        cache[key] = rot
        limit = int(getattr(step, "tpl_cache_limit", 128) or 0)
        if limit > 0:
            while len(cache) > limit:
                try:
                    first_key = next(iter(cache))
                    cache.pop(first_key, None)
                except Exception:
                    break
        return rot

    def _quality_passes(self, step: StepData) -> list[tuple[str, dict | None]]:
        quality = str(getattr(step, "match_quality", "normal") or "normal").lower()
        quality = quality.replace(" ", "_").replace("-", "_")
        passes: list[tuple[str, dict | None]] = []
        seen = set()

        def add_pass(name: str, overrides: dict | None):
            key = self._pp_key(step, overrides)
            if key in seen:
                return
            seen.add(key)
            passes.append((name, overrides))

        add_pass("base", None)
        if quality not in ("high", "high_accuracy", "accuracy", "hq"):
            return passes

        use_color = bool(getattr(step, "match_color", False))
        if use_color:
            return passes
        add_pass("gray", {"force_gray": True, "pre_gray": True})
        add_pass(
            "clahe",
            {"force_gray": True, "pre_gray": True, "pre_clahe": True, "pre_sharpen": True},
        )
        add_pass("edge", {"force_gray": True, "pre_gray": True, "pre_edge": True})
        return passes

    def _orb_fallback(self, img_bgr, tpl_bgr, step, over_budget_cb=None):
        try:
            if over_budget_cb and over_budget_cb():
                return None
            n = int(getattr(step, "feat_nfeatures", 500))
            orb = cv2.ORB_create(nfeatures=max(100, n))
            
            frame = img_bgr
            if getattr(step, "search_roi_enabled", False) and int(getattr(step, "search_roi_width", 0)) > 0 and int(getattr(step, "search_roi_height", 0)) > 0:
                rx = max(0, int(step.search_roi_left))
                ry = max(0, int(step.search_roi_top))
                rw = int(step.search_roi_width)
                rh = int(step.search_roi_height)
                frame = img_bgr[ry:ry+rh, rx:rx+rw]
                
            kp1, des1 = orb.detectAndCompute(tpl_bgr, None)
            kp2, des2 = orb.detectAndCompute(frame, None)
            
            if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
                return None
                
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            matches = bf.knnMatch(des1, des2, k=2)
            
            good = []
            ratio = float(getattr(step, "feat_match_ratio", 0.75))
            for m, n in matches:
                if m.distance < ratio * n.distance:
                    good.append(m)
                    
            if len(good) < 4:
                return None
                
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1,1,2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1,1,2)
            
            thresh = float(getattr(step, "feat_ransac_reproj_thresh", 3.0))
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, thresh)
            
            if M is None:
                return None
                
            h, w = tpl_bgr.shape[:2]
            corners = np.float32([[0,0],[w,0],[w,h],[0,h]]).reshape(-1,1,2)
            trans = cv2.perspectiveTransform(corners, M)
            cx = int(np.mean(trans[:,0,0]))
            cy = int(np.mean(trans[:,0,1]))
            
            inliers = int(mask.sum()) if mask is not None else 0
            min_inliers = 12
            if inliers < min_inliers:
                return None
                
            score = min(1.0, inliers / max(10.0, len(good)))
            return MatchResult(True, cx, cy, score, w, h, stage="feature")
        except Exception:
            import traceback
            traceback.print_exc()
            return None

    def find_best_optimized(self, frame_bgr: np.ndarray, step: StepData) -> MatchResult:
        """Find best match with optional multi-pass preprocessing and timing."""
        try:
            tpl_bgr = step.ensure_tpl()
            if tpl_bgr is None:
                return MatchResult(False)
            th_val = getattr(step, "min_confidence", None)
            if th_val is None:
                th_val = getattr(step, "threshold", 0.85)
            if th_val is None:
                th_val = 0.85
            try:
                th = float(th_val)
            except (TypeError, ValueError):
                th = 0.85
            delta = 0.03
            budget_ms = int(getattr(step, "budget_ms", 0))
            t_all0 = time.perf_counter()
            timing: dict = {}

            def over_budget() -> bool:
                if budget_ms <= 0:
                    return False
                return (time.perf_counter() - t_all0) * 1000.0 > budget_ms

            def add_timing(key: str, start: float) -> None:
                elapsed = (time.perf_counter() - start) * 1000.0
                timing[key] = round(timing.get(key, 0.0) + elapsed, 2)

            def stage_name(base: str, pass_name: str) -> str:
                if pass_name and pass_name != "base":
                    return f"{base}:{pass_name}"
                return base

            def stage_rank(stage: str) -> int:
                base = stage.split(":", 1)[0]
                return {"single": 0, "scale": 1, "rotation": 2, "scale_rot": 3}.get(base, 99)

            def color_gate_passed(img_like, tpl_like, x: int, y: int, overrides: dict | None) -> bool:
                if overrides:
                    if overrides.get("force_gray", False):
                        return True
                    if "match_color" in overrides and not overrides["match_color"]:
                        return True
                return self._color_gate_passed(img_like, tpl_like, x, y, step)

            best_data = None
            best_score = -1.0
            best_rank = 99

            def record_best(score: float, cx: int, cy: int, tpl_like, stage: str, scale: float = 1.0, angle: float = 0.0) -> None:
                nonlocal best_data, best_score, best_rank
                if score < th:
                    return
                rank = stage_rank(stage)
                if score > best_score + 1e-6 or (abs(score - best_score) <= 1e-6 and rank < best_rank):
                    best_score = score
                    best_rank = rank
                    best_data = {
                        "x": cx,
                        "y": cy,
                        "score": score,
                        "w": tpl_like.shape[1],
                        "h": tpl_like.shape[0],
                        "stage": stage,
                        "scale": scale,
                        "angle": angle,
                    }

            def budget_return() -> MatchResult:
                timing["total_ms"] = round((time.perf_counter() - t_all0) * 1000.0, 2)
                if best_data:
                    return MatchResult(
                        True,
                        best_data["x"],
                        best_data["y"],
                        best_data["score"],
                        best_data["w"],
                        best_data["h"],
                        stage=best_data["stage"],
                        scale=best_data["scale"],
                        angle=best_data["angle"],
                        timing=timing,
                    )
                return MatchResult(False, timing=timing)

            k = max(1, int(getattr(step, "top_k", 1)))
            enable_scale = int(getattr(step, "max_scales", 0)) > 0
            enable_rot = int(getattr(step, "max_rotations", 0)) > 0
            quality = str(getattr(step, "match_quality", "normal") or "normal").lower()
            quality = quality.replace(" ", "_").replace("-", "_")
            high_mode = quality in ("high", "high_accuracy", "accuracy", "hq")
            enable_combo = high_mode and enable_scale and enable_rot
            scales = None
            angles = None

            def build_scales():
                smin = max(0.3, float(getattr(step, "ms_min_scale", 0.9)))
                smax = min(3.0, float(getattr(step, "ms_max_scale", 1.1)))
                sstep = max(1.01, float(getattr(step, "ms_step", 1.05)))
                scales_local = [1.0]
                s = 1.0
                while s / sstep >= smin:
                    s /= sstep
                    scales_local.append(s)
                s = 1.0
                while s * sstep <= smax:
                    s *= sstep
                    scales_local.append(s)
                scales_local = sorted(set([round(x, 4) for x in scales_local]), key=lambda v: abs(v - 1.0))
                return scales_local

            def build_angles():
                rmin = float(getattr(step, "rot_min_deg", -10.0))
                rmax = float(getattr(step, "rot_max_deg", 10.0))
                rstep = max(1.0, float(getattr(step, "rot_step_deg", 5.0)))
                angles_local = []
                a = 0.0
                while a - rstep >= rmin:
                    a -= rstep
                    angles_local.append(round(a, 2))
                a = 0.0
                while a + rstep <= rmax:
                    a += rstep
                    angles_local.append(round(a, 2))
                angles_local = sorted(set([round(x, 2) for x in angles_local]), key=lambda v: abs(v))
                return angles_local

            for pass_name, overrides in self._quality_passes(step):
                if over_budget():
                    return budget_return()

                img_pp = _apply_preprocess(frame_bgr, step, overrides)
                tpl_pp = self._get_pp_tpl(tpl_bgr, step, overrides)

                # 1. Single Scale
                t0 = time.perf_counter()
                res = match_template_with_color(img_pp, tpl_pp, step)
                cands = _extract_topk(res, k, tpl_pp.shape[1], tpl_pp.shape[0])
                add_timing("single_ms", t0)

                for (score, x, y) in cands:
                    if not color_gate_passed(img_pp, tpl_pp, x, y, overrides):
                        continue
                    if high_mode:
                        record_best(
                            score,
                            x + tpl_pp.shape[1] // 2,
                            y + tpl_pp.shape[0] // 2,
                            tpl_pp,
                            stage_name("single", pass_name),
                        )
                    elif score >= th:
                        timing["total_ms"] = round((time.perf_counter() - t_all0) * 1000.0, 2)
                        return MatchResult(
                            True,
                            x + tpl_pp.shape[1] // 2,
                            y + tpl_pp.shape[0] // 2,
                            score,
                            tpl_pp.shape[1],
                            tpl_pp.shape[0],
                            stage=stage_name("single", pass_name),
                            timing=timing,
                        )

                if over_budget():
                    return budget_return()

                # 2. Multi Scale
                if enable_scale:
                    if scales is None:
                        scales = build_scales()
                    t0 = time.perf_counter()
                    best_sc = []
                    best_seen = 0.0

                    for sc in scales:
                        if over_budget():
                            break
                        if sc == 1.0:
                            continue
                        tpl_s = self._get_scale_tpl(tpl_pp, step, sc, overrides)
                        if tpl_s is None:
                            continue

                        try:
                            res = match_template_with_color(img_pp, tpl_s, step)
                            cands = _extract_topk(res, k, tpl_s.shape[1], tpl_s.shape[0])
                            for (score, x, y) in cands:
                                if not color_gate_passed(img_pp, tpl_s, x, y, overrides):
                                    continue
                                if high_mode:
                                    record_best(
                                        score,
                                        x + tpl_s.shape[1] // 2,
                                        y + tpl_s.shape[0] // 2,
                                        tpl_s,
                                        stage_name("scale", pass_name),
                                        scale=sc,
                                    )
                                    if score > best_seen:
                                        best_seen = score
                                else:
                                    best_sc.append((score, x, y, sc))
                                    if score > best_seen:
                                        best_seen = score
                        except Exception:
                            continue
                        if (not high_mode) and best_seen >= (th + delta):
                            break

                    add_timing("scale_ms", t0)
                    if not high_mode:
                        best_sc.sort(key=lambda t: t[0], reverse=True)
                        if best_sc and best_sc[0][0] >= th:
                            score, x, y, sc = best_sc[0]
                            tpl_s = self._get_scale_tpl(tpl_pp, step, sc, overrides)
                            timing["total_ms"] = round((time.perf_counter() - t_all0) * 1000.0, 2)
                            return MatchResult(
                                True,
                                x + tpl_s.shape[1] // 2,
                                y + tpl_s.shape[0] // 2,
                                score,
                                tpl_s.shape[1],
                                tpl_s.shape[0],
                                stage=stage_name("scale", pass_name),
                                scale=sc,
                                timing=timing,
                            )

                if over_budget():
                    return budget_return()

                # 3. Rotation
                if enable_rot:
                    if angles is None:
                        angles = build_angles()
                    t0 = time.perf_counter()
                    best_rot = []
                    best_seen = 0.0

                    for ang in angles:
                        if over_budget():
                            break
                        if ang == 0.0:
                            continue
                        tpl_r = self._get_rot_tpl(tpl_pp, step, ang, overrides)
                        try:
                            res = match_template_with_color(img_pp, tpl_r, step)
                            cands = _extract_topk(res, k, tpl_r.shape[1], tpl_r.shape[0])
                            for (score, x, y) in cands:
                                if not color_gate_passed(img_pp, tpl_r, x, y, overrides):
                                    continue
                                if high_mode:
                                    record_best(
                                        score,
                                        x + tpl_r.shape[1] // 2,
                                        y + tpl_r.shape[0] // 2,
                                        tpl_r,
                                        stage_name("rotation", pass_name),
                                        angle=ang,
                                    )
                                    if score > best_seen:
                                        best_seen = score
                                else:
                                    best_rot.append((score, x, y, ang))
                                    if score > best_seen:
                                        best_seen = score
                        except Exception:
                            continue
                        if (not high_mode) and best_seen >= (th + delta):
                            break

                    add_timing("rot_ms", t0)
                    if not high_mode:
                        best_rot.sort(key=lambda t: t[0], reverse=True)
                        if best_rot and best_rot[0][0] >= th:
                            score, x, y, ang = best_rot[0]
                            tpl_r = self._get_rot_tpl(tpl_pp, step, ang, overrides)
                            timing["total_ms"] = round((time.perf_counter() - t_all0) * 1000.0, 2)
                            return MatchResult(
                                True,
                                x + tpl_r.shape[1] // 2,
                                y + tpl_r.shape[0] // 2,
                                score,
                                tpl_r.shape[1],
                                tpl_r.shape[0],
                                stage=stage_name("rotation", pass_name),
                                angle=ang,
                                timing=timing,
                            )

                if over_budget():
                    return budget_return()

                # 4. Scale + Rotation (High Quality)
                if enable_combo:
                    if scales is None:
                        scales = build_scales()
                    if angles is None:
                        angles = build_angles()
                    t0 = time.perf_counter()
                    for sc in scales:
                        if over_budget():
                            break
                        if sc == 1.0:
                            continue
                        tpl_s = self._get_scale_tpl(tpl_pp, step, sc, overrides)
                        if tpl_s is None:
                            continue
                        for ang in angles:
                            if over_budget():
                                break
                            if ang == 0.0:
                                continue
                            tpl_sr = self._get_rot_tpl(
                                tpl_s,
                                step,
                                ang,
                                overrides,
                                extra_key=("scale", float(sc)),
                            )
                            try:
                                res = match_template_with_color(img_pp, tpl_sr, step)
                                cands = _extract_topk(res, k, tpl_sr.shape[1], tpl_sr.shape[0])
                                for (score, x, y) in cands:
                                    if not color_gate_passed(img_pp, tpl_sr, x, y, overrides):
                                        continue
                                    record_best(
                                        score,
                                        x + tpl_sr.shape[1] // 2,
                                        y + tpl_sr.shape[0] // 2,
                                        tpl_sr,
                                        stage_name("scale_rot", pass_name),
                                        scale=sc,
                                        angle=ang,
                                    )
                            except Exception:
                                continue

                    add_timing("scale_rot_ms", t0)

            if over_budget():
                return budget_return()

            if best_data:
                timing["total_ms"] = round((time.perf_counter() - t_all0) * 1000.0, 2)
                return MatchResult(
                    True,
                    best_data["x"],
                    best_data["y"],
                    best_data["score"],
                    best_data["w"],
                    best_data["h"],
                    stage=best_data["stage"],
                    scale=best_data["scale"],
                    angle=best_data["angle"],
                    timing=timing,
                )

            # 5. ORB Fallback
            if getattr(step, "feat_fallback_enable", False):
                t0 = time.perf_counter()
                mr = self._orb_fallback(frame_bgr, tpl_bgr, step, over_budget)
                add_timing("feature_ms", t0)
                if mr and mr.ok and mr.score >= th * 0.9:
                    mr.stage = "feature"
                    mr.timing.update(timing)
                    timing["total_ms"] = round((time.perf_counter() - t_all0) * 1000.0, 2)
                    return mr

            timing["total_ms"] = round((time.perf_counter() - t_all0) * 1000.0, 2)
            return MatchResult(False, timing=timing)
        except Exception:
            import traceback
            traceback.print_exc()
            return MatchResult(False)

    def find_all(self, frame_bgr: np.ndarray, step: StepData) -> list[tuple[int, int, float]]:
        tpl_bgr = step.ensure_tpl()
        if tpl_bgr is None:
            return []

        th = float(getattr(step, "min_confidence", step.threshold))
        tpl_h, tpl_w = tpl_bgr.shape[:2]

        img_pp = _apply_preprocess(frame_bgr, step)
        tpl_pp = self._get_pp_tpl(tpl_bgr, step)

        try:
            res = match_template_with_color(img_pp, tpl_pp, step)
        except cv2.error:
            return []

        loc = np.where(res >= th)
        boxes = []
        for pt in zip(*loc[::-1]):
            score = res[pt[1], pt[0]]
            boxes.append([pt[0], pt[1], pt[0] + tpl_w, pt[1] + tpl_h, score])

        if not boxes:
            return []

        boxes = np.array(boxes)
        suppressed_boxes = self._non_max_suppression(boxes, 0.3)

        results = []
        for (x1, y1, x2, y2, score) in suppressed_boxes:
            if not self._color_gate_passed(img_pp, tpl_pp, x1, y1, step):
                continue
            center_x = x1 + tpl_w // 2
            center_y = y1 + tpl_h // 2
            results.append((center_x, center_y, score))
            
        results.sort(key=lambda item: (item[1], item[0]))
        return results

    def _non_max_suppression(self, boxes, overlapThresh):
        if len(boxes) == 0:
            return []
        if boxes.dtype.kind == "i":
            boxes = boxes.astype("float")
        
        pick = []
        x1 = boxes[:,0]
        y1 = boxes[:,1]
        x2 = boxes[:,2]
        y2 = boxes[:,3]
        scores = boxes[:,4]
        area = (x2 - x1 + 1) * (y2 - y1 + 1)
        idxs = np.argsort(scores)
        
        while len(idxs) > 0:
            last = len(idxs) - 1
            i = idxs[last]
            pick.append(i)
            
            xx1 = np.maximum(x1[i], x1[idxs[:last]])
            yy1 = np.maximum(y1[i], y1[idxs[:last]])
            xx2 = np.minimum(x2[i], x2[idxs[:last]])
            yy2 = np.minimum(y2[i], y2[idxs[:last]])
            
            w = np.maximum(0, xx2 - xx1 + 1)
            h = np.maximum(0, yy2 - yy1 + 1)
            
            overlap = (w * h) / area[idxs[:last]]
            
            idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > overlapThresh)[0])))
            
        return boxes[pick].astype("int")
