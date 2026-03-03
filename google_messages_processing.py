from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import dateparser
import pandas as pd

from config import CONFIG, SELECTORS
from data_handler import DataHandler


class GoogleMessagesProcessingMixin:
    def process_messages(
        self, save_path: Path, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> Tuple[int, int]:
        """메시지 파싱 및 저장"""
        if self._is_page_closed():
            logging.error("페이지가 닫혀 메시지 처리를 중단합니다.")
            return (0, 0)

        self.scroll_down_slowly()
        self.wait_for_dom_stability()

        all_elements = self.page.locator(SELECTORS["ALL_MSG_ITEMS"]).all()
        logging.info(f"스캔된 전체 요소 수: {len(all_elements)}")

        current_base_date = None
        msg_index_counter = 0
        final_rows = []
        audit_logs = []
        total_saved_img_count = 0
        date_summary = {
            "saved_count": 0,
            "missing_date_count": 0,
            "min_date": None,
            "max_date": None,
            "tombstone_seen": 0,
            "time_found": 0,
        }

        for element in all_elements:
            try:
                tag_name = element.evaluate("el => el.tagName.toLowerCase()")

                if "tombstone" in tag_name:
                    date_summary["tombstone_seen"] += 1
                    try:
                        ts_el = element.locator(SELECTORS["TOMBSTONE_DATE"]).first
                        if ts_el.is_visible():
                            date_text = ts_el.inner_text().strip()
                            ymd_match = re.search(
                                r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", date_text
                            )
                            md_match = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", date_text)

                            parsed_base = None
                            if ymd_match:
                                parsed_base = datetime(
                                    int(ymd_match.group(1)),
                                    int(ymd_match.group(2)),
                                    int(ymd_match.group(3)),
                                )
                            elif md_match:
                                now = datetime.now()
                                parsed_base = datetime(
                                    now.year,
                                    int(md_match.group(1)),
                                    int(md_match.group(2)),
                                )
                            else:
                                parsed = dateparser.parse(
                                    date_text,
                                    languages=["ko"],
                                    settings={"RELATIVE_BASE": datetime.now()},
                                )
                                if parsed:
                                    parsed_base = parsed

                            if parsed_base:
                                current_base_date = parsed_base

                            self._debug_date_log(
                                "tombstone_parse",
                                text=date_text,
                                ymd=bool(ymd_match),
                                md=bool(md_match),
                                parsed=parsed_base.isoformat() if parsed_base else None,
                            )
                    except Exception as exc:
                        logging.debug("tombstone 파싱 실패(index=%d): %s", msg_index_counter, exc)
                    continue

                msg_date = current_base_date
                found_time_part = None
                debug_candidates = []
                try:
                    candidates = element.evaluate(
                        """el => {
                        let texts = [];
                        if (el.getAttribute('aria-label')) texts.push(el.getAttribute('aria-label'));
                        const labels = el.querySelectorAll('[aria-label]');
                        labels.forEach(t => texts.push(t.getAttribute('aria-label')));
                        const times = el.querySelectorAll('.timestamp, mws-absolute-timestamp, mws-relative-timestamp');
                        times.forEach(t => texts.push(t.innerText));
                        texts.push(el.innerText);
                        return texts;
                    }"""
                    )

                    if CONFIG.get("DEBUG_DATE_PARSE"):
                        debug_candidates = [c for c in candidates if c]

                    time_patterns = [
                        r"((오전|오후)\s*\d{1,2}:\d{2})",
                        r"((AM|PM)\s*\d{1,2}:\d{2})",
                        r"(\d{1,2}:\d{2})",
                    ]
                    for text in candidates:
                        if not text:
                            continue
                        clean = re.sub(r"[\n\r\t\xa0]", " ", text)
                        for pat in time_patterns:
                            match = re.search(pat, clean, re.IGNORECASE)
                            if match:
                                parsed_time = dateparser.parse(match.group(0), languages=["ko", "en"])
                                if parsed_time:
                                    found_time_part = parsed_time
                                    break
                        if found_time_part:
                            break
                except Exception as exc:
                    logging.debug("시간 파싱 후보 수집 실패(index=%d): %s", msg_index_counter, exc)

                if msg_date and found_time_part:
                    msg_date = msg_date.replace(
                        hour=found_time_part.hour,
                        minute=found_time_part.minute,
                        second=found_time_part.second,
                    )

                if found_time_part:
                    date_summary["time_found"] += 1

                if CONFIG.get("DEBUG_DATE_PARSE") and (
                    current_base_date is None or found_time_part is None
                ):
                    debug_text_content = None
                    debug_text_preview = None
                    try:
                        debug_text_content = element.evaluate("el => el.textContent")
                    except Exception as exc:
                        logging.debug("디버그 textContent 수집 실패(index=%d): %s", msg_index_counter, exc)
                    try:
                        debug_text_preview = element.inner_text()
                    except Exception as exc:
                        logging.debug("디버그 inner_text 수집 실패(index=%d): %s", msg_index_counter, exc)

                    missing_parts = []
                    if current_base_date is None:
                        missing_parts.append("base_date")
                    if found_time_part is None:
                        missing_parts.append("time")

                    self._debug_date_log(
                        "date_parse_missing",
                        missing=",".join(missing_parts) if missing_parts else None,
                        msg_index=msg_index_counter,
                        tag=tag_name,
                        base_date=current_base_date.isoformat() if current_base_date else None,
                        time_found=found_time_part.strftime("%H:%M:%S") if found_time_part else None,
                        candidates=debug_candidates,
                        text_content=debug_text_content,
                        text_preview=debug_text_preview,
                    )

                if msg_date:
                    if start_date and msg_date < start_date:
                        continue
                    if end_date and msg_date > end_date:
                        continue

                text = element.inner_text().replace("\n", " ")
                class_attr = element.get_attribute("class") or ""
                sender = "나" if "outgoing" in class_attr else "상대방"

                attachment_info_parts = []
                saved_image_files = []
                saved_img_count = 0

                thumbnails = element.locator("img").all()
                detected_img_count = len(thumbnails)
                for i, thumb in enumerate(thumbnails):
                    try:
                        thumb.scroll_into_view_if_needed()
                        for _ in range(30):
                            if thumb.evaluate("el => el.naturalWidth > 0"):
                                break
                            self.page.wait_for_timeout(100)

                        src = thumb.get_attribute("src")
                        if src and "blob:" in src:
                            fname = DataHandler.build_attachment_filename(
                                msg_date, msg_index_counter, f"img_{i+1}", src, ".jpg"
                            )
                            fpath = save_path / fname
                            if DataHandler.save_blob_to_file(self.page, src, fpath):
                                attachment_info_parts.append(f"[{fname}]")
                                saved_image_files.append(fname)
                                saved_img_count += 1
                    except Exception as e:
                        logging.warning(f"이미지 저장 실패: {e}")

                video_elements = element.locator("video").all()
                for i, video in enumerate(video_elements):
                    try:
                        video.scroll_into_view_if_needed()
                    except Exception as exc:
                        logging.debug(
                            "비디오 스크롤 실패(index=%d, video=%d): %s",
                            msg_index_counter,
                            i + 1,
                            exc,
                        )
                    src = video.get_attribute("src")
                    if not src:
                        try:
                            src = video.locator("source").first.get_attribute("src")
                        except Exception as exc:
                            logging.debug(
                                "비디오 source 추출 실패(index=%d, video=%d): %s",
                                msg_index_counter,
                                i + 1,
                                exc,
                            )
                    fname = DataHandler.build_attachment_filename(
                        msg_date, msg_index_counter, f"video_{i+1}", src, ".mp4"
                    )
                    fpath = save_path / fname
                    if src and DataHandler.save_blob_to_file(self.page, src, fpath):
                        attachment_info_parts.append(f"[video:{fname}]")
                    elif fname:
                        attachment_info_parts.append(f"[video:{fname}:미저장]")

                audio_elements = element.locator("audio").all()
                for i, audio in enumerate(audio_elements):
                    try:
                        audio.scroll_into_view_if_needed()
                    except Exception as exc:
                        logging.debug(
                            "오디오 스크롤 실패(index=%d, audio=%d): %s",
                            msg_index_counter,
                            i + 1,
                            exc,
                        )
                    src = audio.get_attribute("src")
                    if not src:
                        try:
                            src = audio.locator("source").first.get_attribute("src")
                        except Exception as exc:
                            logging.debug(
                                "오디오 source 추출 실패(index=%d, audio=%d): %s",
                                msg_index_counter,
                                i + 1,
                                exc,
                            )
                    fname = DataHandler.build_attachment_filename(
                        msg_date, msg_index_counter, f"audio_{i+1}", src, ".mp3"
                    )
                    fpath = save_path / fname
                    if src and DataHandler.save_blob_to_file(self.page, src, fpath):
                        attachment_info_parts.append(f"[audio:{fname}]")
                    elif fname:
                        attachment_info_parts.append(f"[audio:{fname}:미저장]")

                download_links = element.locator("a[download]").all()
                for i, link in enumerate(download_links):
                    try:
                        link.scroll_into_view_if_needed()
                    except Exception as exc:
                        logging.debug(
                            "다운로드 링크 스크롤 실패(index=%d, file=%d): %s",
                            msg_index_counter,
                            i + 1,
                            exc,
                        )
                    href = link.get_attribute("href")
                    name_hint = link.get_attribute("download") or link.inner_text().strip()
                    base_label = f"file_{i+1}"
                    if name_hint:
                        stem = Path(name_hint).stem
                        base_label = (
                            f"{base_label}_{DataHandler.sanitize_filename(stem, '')}".strip("_")
                            or base_label
                        )
                    fname = DataHandler.build_attachment_filename(
                        msg_date, msg_index_counter, base_label, href, ".bin"
                    )
                    fpath = save_path / fname
                    if href and DataHandler.save_blob_to_file(self.page, href, fpath):
                        attachment_info_parts.append(f"[file:{fname}]")
                    elif fname:
                        attachment_info_parts.append(f"[file:{fname}:미저장]")

                total_saved_img_count += saved_img_count
                attachment_info = " ".join(attachment_info_parts).strip()

                if text.strip() or attachment_info:
                    date_str = msg_date.strftime("%Y-%m-%d %H:%M") if msg_date else "날짜불명"
                    final_rows.append(
                        {
                            "날짜": date_str,
                            "보낸 사람": sender,
                            "내용": text,
                            "첨부파일": attachment_info,
                            "이미지목록": saved_image_files,
                        }
                    )
                    date_summary["saved_count"] += 1
                    if msg_date:
                        if not date_summary["min_date"] or msg_date < date_summary["min_date"]:
                            date_summary["min_date"] = msg_date
                        if not date_summary["max_date"] or msg_date > date_summary["max_date"]:
                            date_summary["max_date"] = msg_date
                    else:
                        date_summary["missing_date_count"] += 1

                    status = "✅완벽" if saved_img_count == detected_img_count else "❌누락"
                    audit_logs.append(
                        {
                            "날짜": date_str,
                            "내용요약": text[:20],
                            "이미지_발견": detected_img_count,
                            "이미지_저장": saved_img_count,
                            "상태": status,
                        }
                    )

                msg_index_counter += 1
            except Exception as e:
                logging.error(f"메시지 처리 중 에러: {e}")
                continue

        self._debug_date_log(
            "date_summary",
            save_dir=str(save_path),
            saved=date_summary["saved_count"],
            missing=date_summary["missing_date_count"],
            min_date=date_summary["min_date"].isoformat() if date_summary["min_date"] else None,
            max_date=date_summary["max_date"].isoformat() if date_summary["max_date"] else None,
            tombstone_seen=date_summary["tombstone_seen"],
            time_found=date_summary["time_found"],
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )

        if not final_rows:
            logging.info("저장할 데이터가 없습니다.")
            return (0, 0)

        logging.info(f"총 {len(final_rows)}건 데이터 저장 중...")
        final_rows.sort(key=lambda x: x["날짜"])
        df = pd.DataFrame(final_rows)
        save_df = df[["날짜", "보낸 사람", "내용", "첨부파일"]]
        excel_path = save_path / "chat_log.xlsx"
        save_df.to_excel(excel_path, index=False)

        DataHandler.embed_images_to_excel(excel_path, save_path, final_rows)

        if audit_logs:
            audit_df = pd.DataFrame(audit_logs)
            audit_df.to_csv(save_path / "검수보고서.csv", index=False, encoding="utf-8-sig")

        (save_path / "작업완료.txt").touch()
        return (len(final_rows), total_saved_img_count)
