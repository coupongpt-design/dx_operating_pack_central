from __future__ import annotations

import copy
import json
from pathlib import Path


OUT_PATH = Path("app/core/scenario_wizard_templates.json")


def field(name: str, label: str, ftype: str = "str", **kwargs):
    item = {"name": name, "label": label, "type": ftype}
    item.update(kwargs)
    return item


def clone_fields(items: list[dict]) -> list[dict]:
    return [copy.deepcopy(x) for x in items]


def set_default(items: list[dict], field_name: str, value):
    for item in items:
        if item.get("name") == field_name:
            item["default"] = value
            return


def replace_field(items: list[dict], field_name: str, new_field: dict):
    for idx, item in enumerate(items):
        if item.get("name") == field_name:
            items[idx] = new_field
            return


TEMPLATES: list[dict] = []


def add_template(
    template_id: str,
    title: str,
    summary: str,
    fields: list[dict],
    *,
    difficulty: str = "beginner",
    recommended: bool = True,
    tags: list[str] | None = None,
    prerequisites: list[str] | None = None,
    failure_points: list[str] | None = None,
    builder: str | None = None,
):
    item = {
        "id": template_id,
        "title": title,
        "summary": summary,
        "difficulty": difficulty,
        "recommended": recommended,
        "tags": tags or [],
        "prerequisites": prerequisites or [],
        "failure_points": failure_points or [],
        "fields": fields,
    }
    if builder:
        item["builder"] = builder
    TEMPLATES.append(item)


KEY_OPTIONS = [
    {"label": "Enter", "value": "enter"},
    {"label": "Tab", "value": "tab"},
    {"label": "Space", "value": "space"},
]

CLICK_BTN_OPTIONS = [
    {"label": "Left", "value": "left"},
    {"label": "Right", "value": "right"},
    {"label": "Middle", "value": "middle"},
]

OCR_PREPROCESS_OPTIONS = [
    {"label": "Otsu", "value": "otsu"},
    {"label": "Adaptive", "value": "adaptive"},
    {"label": "None", "value": "none"},
]

SAFE_OPERATOR_OPTIONS = [
    {"label": ">", "value": ">"},
    {"label": ">=", "value": ">="},
    {"label": "<", "value": "<"},
    {"label": "<=", "value": "<="},
]

CONDITION_OPERATOR_OPTIONS = [
    {"label": "<=", "value": "<="},
    {"label": "<", "value": "<"},
    {"label": ">", "value": ">"},
    {"label": ">=", "value": ">="},
    {"label": "==", "value": "=="},
]


chat_fields = [
    field("scenario_name", "시나리오 이름", default="채팅 반복 전송"),
    field("message_text", "보낼 문장", required=True),
    field("submit_key", "전송 키", "choice", options=KEY_OPTIONS, default="enter"),
    field("repeat_count", "반복 횟수 (0=무한)", "int", min=0, max=100000, default=10),
    field("delay_ms", "전송 간격(ms)", "int", min=0, max=600000, default=200),
]

add_template(
    "chat_repeater",
    "채팅 문장 반복 전송",
    "같은 문장을 여러 번 입력하고 전송합니다.",
    clone_fields(chat_fields),
    tags=["채팅", "입력", "반복"],
    prerequisites=["입력창에 커서를 먼저 맞추세요."],
    failure_points=["전송 키가 잘못되면 메시지가 전송되지 않습니다."],
)

quick_burst_fields = clone_fields(chat_fields)
set_default(quick_burst_fields, "scenario_name", "짧은 메시지 빠르게 전송")
set_default(quick_burst_fields, "repeat_count", 30)
set_default(quick_burst_fields, "delay_ms", 50)
add_template(
    "message_quick_burst",
    "짧은 메시지 빠르게 전송",
    "짧은 간격으로 같은 문장을 빠르게 보냅니다.",
    quick_burst_fields,
    tags=["채팅", "입력", "빠른반복"],
    builder="chat_repeater",
)

slow_chat_fields = clone_fields(chat_fields)
set_default(slow_chat_fields, "scenario_name", "채팅 천천히 반복")
set_default(slow_chat_fields, "repeat_count", 5)
set_default(slow_chat_fields, "delay_ms", 1000)
add_template(
    "chat_repeater_slow",
    "채팅 문장 천천히 반복",
    "긴 간격으로 메시지를 반복 전송합니다.",
    slow_chat_fields,
    tags=["채팅", "입력", "안정"],
    builder="chat_repeater",
)

data_loop_fields = [
    field(
        "scenario_name",
        "시나리오 이름",
        default="CSV 행별 서브매크로 실행",
    ),
    field(
        "data_file_path",
        "CSV 파일 경로",
        "path",
        required=True,
        must_exist=True,
        browse_mode="open_file",
        file_filter="CSV Files (*.csv);;All Files (*)",
    ),
    field(
        "sub_macro_path",
        "실행할 매크로 파일",
        "path",
        required=True,
        must_exist=True,
        browse_mode="open_file",
        file_filter="Macro Files (*.macro *.json);;All Files (*)",
    ),
    field("row_delay_ms", "행 간 대기(ms)", "int", min=0, max=600000, default=200),
]

add_template(
    "data_driven_submacro_loop",
    "CSV 각 행으로 서브매크로 실행",
    "CSV 데이터를 읽고 각 행마다 지정한 매크로를 실행합니다.",
    clone_fields(data_loop_fields),
    difficulty="advanced",
    tags=["CSV", "서브매크로", "반복"],
    prerequisites=["CSV 형식이 실행 로직과 맞아야 합니다."],
)

csv_text_fields = [
    field("scenario_name", "시나리오 이름", default="CSV 텍스트 전송"),
    field(
        "data_file_path",
        "CSV 파일 경로",
        "path",
        required=True,
        must_exist=True,
        browse_mode="open_file",
        file_filter="CSV Files (*.csv);;All Files (*)",
    ),
    field(
        "text_pattern",
        "입력 패턴",
        default="{data}",
        placeholder="{data} 또는 {col1} 같은 치환 토큰 사용",
    ),
    field("submit_key", "전송 키", "choice", options=KEY_OPTIONS, default="enter"),
    field("row_delay_ms", "행 간 대기(ms)", "int", min=0, max=600000, default=200),
]

add_template(
    "csv_text_submit_loop",
    "CSV 내용 한 줄씩 입력 후 전송",
    "CSV 각 행을 텍스트로 입력하고 전송 키를 누릅니다.",
    clone_fields(csv_text_fields),
    difficulty="intermediate",
    tags=["CSV", "입력", "전송"],
)

csv_tab_fields = clone_fields(csv_text_fields)
set_default(csv_tab_fields, "scenario_name", "CSV 내용 탭 제출")
set_default(csv_tab_fields, "submit_key", "tab")
add_template(
    "csv_text_submit_loop_tab",
    "CSV 내용 입력 후 탭 이동",
    "CSV 각 행을 입력한 뒤 탭 키로 다음 칸으로 이동합니다.",
    csv_tab_fields,
    difficulty="intermediate",
    tags=["CSV", "입력", "탭"],
    builder="csv_text_submit_loop",
)

submacro_retry_fields = [
    field("scenario_name", "시나리오 이름", default="서브매크로 재시도"),
    field(
        "sub_macro_path",
        "실행할 매크로 파일",
        "path",
        required=True,
        must_exist=True,
        browse_mode="open_file",
        file_filter="Macro Files (*.macro *.json);;All Files (*)",
    ),
    field("retry_count", "재시도 횟수 (0=무한)", "int", min=0, max=100000, default=3),
    field("retry_interval_ms", "재시도 간격(ms)", "int", min=0, max=600000, default=300),
]

add_template(
    "submacro_retry_loop",
    "서브매크로 반복 재실행",
    "같은 매크로를 일정 횟수 반복 실행합니다.",
    clone_fields(submacro_retry_fields),
    difficulty="intermediate",
    tags=["서브매크로", "반복", "재시도"],
)

submacro_infinite_fields = clone_fields(submacro_retry_fields)
set_default(submacro_infinite_fields, "scenario_name", "서브매크로 무한반복")
set_default(submacro_infinite_fields, "retry_count", 0)
add_template(
    "submacro_infinite_loop",
    "서브매크로 무한 반복",
    "중지할 때까지 같은 매크로를 계속 실행합니다.",
    submacro_infinite_fields,
    difficulty="intermediate",
    tags=["서브매크로", "무한반복"],
    failure_points=["중지 키를 준비하지 않으면 수동 종료가 필요할 수 있습니다."],
    builder="submacro_retry_loop",
)

run_once_fields = [
    field("scenario_name", "시나리오 이름", default="서브매크로 1회 실행"),
    field(
        "sub_macro_path",
        "실행할 매크로 파일",
        "path",
        required=True,
        must_exist=True,
        browse_mode="open_file",
        file_filter="Macro Files (*.macro *.json);;All Files (*)",
    ),
]

add_template(
    "run_macro_once",
    "서브매크로 한 번 실행",
    "지정한 서브매크로를 1회 실행합니다.",
    clone_fields(run_once_fields),
    tags=["서브매크로", "단일실행"],
    recommended=False,
)

run_two_fields = [
    field("scenario_name", "시나리오 이름", default="매크로 2개 순차 실행"),
    field(
        "macro_path_a",
        "첫 번째 매크로",
        "path",
        required=True,
        must_exist=True,
        browse_mode="open_file",
        file_filter="Macro Files (*.macro *.json);;All Files (*)",
    ),
    field(
        "macro_path_b",
        "두 번째 매크로",
        "path",
        required=True,
        must_exist=True,
        browse_mode="open_file",
        file_filter="Macro Files (*.macro *.json);;All Files (*)",
    ),
    field("wait_between_ms", "중간 대기(ms)", "int", min=0, max=600000, default=200),
]

add_template(
    "run_macro_chain_two",
    "매크로 두 개 이어서 실행",
    "첫 번째 매크로 실행 후 대기하고 두 번째 매크로를 실행합니다.",
    clone_fields(run_two_fields),
    difficulty="intermediate",
    tags=["서브매크로", "체인"],
    builder="run_two_macros",
)

keyboard_combo_fields = [
    field("scenario_name", "시나리오 이름", default="문장 + 단축키 반복"),
    field("before_text", "먼저 입력할 문장", default=""),
    field("hotkey", "단축키", required=True, default="ctrl+s"),
    field("after_text", "나중에 입력할 문장", default=""),
    field("repeat_count", "반복 횟수 (0=무한)", "int", min=0, max=100000, default=3),
    field("cycle_wait_ms", "사이클 대기(ms)", "int", min=0, max=600000, default=300),
]

add_template(
    "keyboard_combo_sequence",
    "문장 입력 후 단축키 반복",
    "문장 입력과 단축키를 한 사이클로 묶어 반복합니다.",
    clone_fields(keyboard_combo_fields),
    difficulty="intermediate",
    tags=["키보드", "단축키", "반복"],
)

hotkey_repeat_fields = [
    field("scenario_name", "시나리오 이름", default="단축키 반복"),
    field("hotkey", "단축키", required=True, default="ctrl+s"),
    field("repeat_count", "반복 횟수 (0=무한)", "int", min=0, max=100000, default=5),
    field("interval_ms", "반복 간격(ms)", "int", min=0, max=600000, default=200),
]

add_template(
    "hotkey_repeat_basic",
    "단축키 반복 실행",
    "같은 단축키를 일정 간격으로 반복 입력합니다.",
    clone_fields(hotkey_repeat_fields),
    tags=["단축키", "반복"],
    builder="hotkey_repeat",
)

alt_tab_fields = clone_fields(hotkey_repeat_fields)
set_default(alt_tab_fields, "scenario_name", "창 전환 반복")
set_default(alt_tab_fields, "hotkey", "alt+tab")
add_template(
    "alt_tab_repeat",
    "창 전환 반복",
    "Alt+Tab을 반복 입력해 창 전환을 자동화합니다.",
    alt_tab_fields,
    tags=["창전환", "단축키"],
    builder="hotkey_repeat",
)

ctrl_s_fields = clone_fields(hotkey_repeat_fields)
set_default(ctrl_s_fields, "scenario_name", "저장 단축키 반복")
set_default(ctrl_s_fields, "hotkey", "ctrl+s")
set_default(ctrl_s_fields, "interval_ms", 1000)
add_template(
    "ctrl_s_repeat",
    "저장 단축키 주기 실행",
    "Ctrl+S를 주기적으로 눌러 저장을 자동화합니다.",
    ctrl_s_fields,
    tags=["저장", "단축키"],
    builder="hotkey_repeat",
)

key_hold_fields = [
    field("scenario_name", "시나리오 이름", default="키 누르고 유지 반복"),
    field("hotkey", "유지할 키", required=True, default="space"),
    field("hold_ms", "유지 시간(ms)", "int", min=1, max=600000, default=300),
    field("repeat_count", "반복 횟수 (0=무한)", "int", min=0, max=100000, default=5),
    field("interval_ms", "반복 간격(ms)", "int", min=0, max=600000, default=200),
]

add_template(
    "key_hold_repeat_basic",
    "키 길게 누르기 반복",
    "같은 키를 지정 시간 동안 누른 뒤 반복합니다.",
    clone_fields(key_hold_fields),
    difficulty="intermediate",
    tags=["키유지", "반복"],
    builder="key_hold_repeat",
)

space_hold_fields = clone_fields(key_hold_fields)
set_default(space_hold_fields, "scenario_name", "스페이스 유지 반복")
set_default(space_hold_fields, "hotkey", "space")
set_default(space_hold_fields, "hold_ms", 600)
add_template(
    "space_hold_repeat",
    "스페이스 길게 누르기 반복",
    "스페이스 키를 길게 누르는 동작을 반복합니다.",
    space_hold_fields,
    difficulty="intermediate",
    tags=["스페이스", "키유지"],
    builder="key_hold_repeat",
)

text_then_hotkey_fields = [
    field("scenario_name", "시나리오 이름", default="문장 입력 후 단축키"),
    field("text", "입력할 문장", required=True, default="테스트"),
    field("wait_ms", "입력 후 대기(ms)", "int", min=0, max=600000, default=100),
    field("hotkey", "뒤이어 누를 키", required=True, default="enter"),
]

add_template(
    "text_then_hotkey",
    "문장 입력 후 단축키 실행",
    "문장을 입력한 뒤 지정한 키를 누릅니다.",
    clone_fields(text_then_hotkey_fields),
    tags=["입력", "단축키"],
)

text_submit_fields = [
    field("scenario_name", "시나리오 이름", default="문장 입력 후 전송"),
    field("text", "입력할 문장", required=True, default="안녕하세요"),
    field("submit_key", "전송 키", "choice", options=KEY_OPTIONS, default="enter"),
    field("after_wait_ms", "전송 후 대기(ms)", "int", min=0, max=600000, default=0),
]

add_template(
    "text_submit_once",
    "문장 한 번 입력하고 전송",
    "문장 입력 후 Enter/Tab/Space 중 하나를 눌러 제출합니다.",
    clone_fields(text_submit_fields),
    tags=["입력", "전송"],
)

click_repeat_fields = [
    field("scenario_name", "시나리오 이름", default="지정 위치 클릭 반복"),
    field("click_x", "클릭 X", "int", min=0, max=100000, default=500),
    field("click_y", "클릭 Y", "int", min=0, max=100000, default=500),
    field("click_btn", "클릭 버튼", "choice", options=CLICK_BTN_OPTIONS, default="left"),
    field("double_click", "더블클릭", "bool", default=False),
    field("repeat_count", "반복 횟수 (0=무한)", "int", min=0, max=100000, default=10),
    field("interval_ms", "클릭 간격(ms)", "int", min=0, max=600000, default=150),
]

add_template(
    "click_repeat_basic",
    "한 위치 계속 클릭",
    "같은 좌표를 반복 클릭합니다.",
    clone_fields(click_repeat_fields),
    tags=["마우스", "클릭", "반복"],
    builder="click_repeat",
)

click_right_fields = clone_fields(click_repeat_fields)
set_default(click_right_fields, "scenario_name", "오른쪽 클릭 반복")
set_default(click_right_fields, "click_btn", "right")
add_template(
    "click_repeat_right",
    "한 위치 오른쪽 클릭 반복",
    "같은 좌표를 오른쪽 버튼으로 반복 클릭합니다.",
    click_right_fields,
    tags=["마우스", "우클릭", "반복"],
    builder="click_repeat",
)

click_double_fields = clone_fields(click_repeat_fields)
set_default(click_double_fields, "scenario_name", "더블클릭 반복")
set_default(click_double_fields, "double_click", True)
set_default(click_double_fields, "interval_ms", 300)
add_template(
    "click_repeat_double",
    "한 위치 더블클릭 반복",
    "같은 좌표를 더블클릭으로 반복합니다.",
    click_double_fields,
    tags=["마우스", "더블클릭", "반복"],
    builder="click_repeat",
)

two_points_fields = [
    field("scenario_name", "시나리오 이름", default="두 지점 번갈아 클릭"),
    field("point1_x", "첫 번째 X", "int", min=0, max=100000, default=500),
    field("point1_y", "첫 번째 Y", "int", min=0, max=100000, default=500),
    field("point2_x", "두 번째 X", "int", min=0, max=100000, default=700),
    field("point2_y", "두 번째 Y", "int", min=0, max=100000, default=500),
    field("repeat_count", "반복 횟수 (0=무한)", "int", min=0, max=100000, default=5),
    field("interval_ms", "사이클 간격(ms)", "int", min=0, max=600000, default=200),
]

add_template(
    "click_two_points_loop",
    "두 위치 번갈아 클릭",
    "A 지점과 B 지점을 순서대로 클릭하는 루프를 만듭니다.",
    clone_fields(two_points_fields),
    difficulty="intermediate",
    tags=["마우스", "클릭", "두지점"],
)

click_hotkey_fields = [
    field("scenario_name", "시나리오 이름", default="클릭 후 단축키"),
    field("click_x", "클릭 X", "int", min=0, max=100000, default=500),
    field("click_y", "클릭 Y", "int", min=0, max=100000, default=500),
    field("click_btn", "클릭 버튼", "choice", options=CLICK_BTN_OPTIONS, default="left"),
    field("double_click", "더블클릭", "bool", default=False),
    field("wait_ms", "클릭 후 대기(ms)", "int", min=0, max=600000, default=100),
    field("hotkey", "눌러줄 키", required=True, default="enter"),
]

add_template(
    "click_then_hotkey",
    "클릭 후 키 입력",
    "지정 위치를 클릭한 뒤 키를 입력합니다.",
    clone_fields(click_hotkey_fields),
    tags=["마우스", "키입력"],
)

click_text_fields = [
    field("scenario_name", "시나리오 이름", default="클릭 후 텍스트 입력"),
    field("click_x", "클릭 X", "int", min=0, max=100000, default=500),
    field("click_y", "클릭 Y", "int", min=0, max=100000, default=500),
    field("click_btn", "클릭 버튼", "choice", options=CLICK_BTN_OPTIONS, default="left"),
    field("double_click", "더블클릭", "bool", default=False),
    field("wait_ms", "클릭 후 대기(ms)", "int", min=0, max=600000, default=100),
    field("text", "입력할 텍스트", required=True, default="테스트"),
]

add_template(
    "click_then_text",
    "클릭 후 텍스트 입력",
    "입력창 클릭 후 지정한 텍스트를 타이핑합니다.",
    clone_fields(click_text_fields),
    tags=["마우스", "입력"],
)

scroll_fields = [
    field("scenario_name", "시나리오 이름", default="스크롤 반복"),
    field("repeat_count", "반복 횟수 (0=무한)", "int", min=0, max=100000, default=5),
    field("scroll_dx", "가로 스크롤", "int", min=-10000, max=10000, default=0),
    field("scroll_dy", "세로 스크롤", "int", min=-10000, max=10000, default=-300),
    field("scroll_times", "한 번에 스크롤 횟수", "int", min=1, max=1000, default=1),
    field("scroll_step_interval_ms", "스크롤 내부 간격(ms)", "int", min=0, max=600000, default=0),
    field("cycle_wait_ms", "사이클 간격(ms)", "int", min=0, max=600000, default=150),
]

add_template(
    "scroll_repeat_down",
    "아래로 스크롤 반복",
    "목록을 아래 방향으로 반복 스크롤합니다.",
    clone_fields(scroll_fields),
    tags=["스크롤", "반복"],
    builder="scroll_repeat",
)

scroll_up_fields = clone_fields(scroll_fields)
set_default(scroll_up_fields, "scenario_name", "위로 스크롤 반복")
set_default(scroll_up_fields, "scroll_dy", 300)
add_template(
    "scroll_repeat_up",
    "위로 스크롤 반복",
    "목록을 위 방향으로 반복 스크롤합니다.",
    scroll_up_fields,
    tags=["스크롤", "반복"],
    builder="scroll_repeat",
)

drag_fields = [
    field("scenario_name", "시나리오 이름", default="드래그 1회"),
    field("drag_from_x", "시작 X", "int", min=0, max=100000, default=500),
    field("drag_from_y", "시작 Y", "int", min=0, max=100000, default=500),
    field("drag_to_x", "끝 X", "int", min=0, max=100000, default=800),
    field("drag_to_y", "끝 Y", "int", min=0, max=100000, default=500),
    field("drag_duration_ms", "드래그 시간(ms)", "int", min=1, max=600000, default=250),
]

add_template(
    "drag_once",
    "드래그 한 번 실행",
    "한 번의 드래그 동작을 생성합니다.",
    clone_fields(drag_fields),
    difficulty="intermediate",
    tags=["드래그", "마우스"],
)

wait_hotkey_fields = [
    field("scenario_name", "시나리오 이름", default="대기 후 단축키 반복"),
    field("repeat_count", "반복 횟수 (0=무한)", "int", min=0, max=100000, default=5),
    field("wait_ms", "실행 전 대기(ms)", "int", min=0, max=600000, default=500),
    field("hotkey", "단축키", required=True, default="f5"),
    field("post_wait_ms", "실행 후 대기(ms)", "int", min=0, max=600000, default=0),
]

add_template(
    "wait_hotkey_repeat",
    "대기 후 단축키 반복",
    "지정 시간 대기 후 단축키를 반복 실행합니다.",
    clone_fields(wait_hotkey_fields),
    difficulty="intermediate",
    tags=["대기", "단축키", "반복"],
)

screenshot_once_fields = [
    field(
        "scenario_name",
        "시나리오 이름",
        default="스크린샷 1장 저장",
    ),
    field(
        "save_path",
        "저장 파일 경로",
        "path",
        required=True,
        browse_mode="save_file",
        file_filter="Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        default="capture_once.png",
    ),
    field("roi_x", "ROI X (0=전체)", "int", min=0, max=100000, default=0),
    field("roi_y", "ROI Y (0=전체)", "int", min=0, max=100000, default=0),
    field("roi_w", "ROI W (0=전체)", "int", min=0, max=100000, default=0),
    field("roi_h", "ROI H (0=전체)", "int", min=0, max=100000, default=0),
]

add_template(
    "screenshot_once",
    "스크린샷 한 장 저장",
    "지정 영역 또는 전체 화면을 한 번 저장합니다.",
    clone_fields(screenshot_once_fields),
    tags=["스크린샷", "저장"],
    builder="screenshot_once",
)

periodic_capture_fields = [
    field("scenario_name", "시나리오 이름", default="주기 스크린샷 저장"),
    field(
        "save_path_pattern",
        "저장 패턴 경로",
        "path",
        required=True,
        browse_mode="save_file",
        file_filter="Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        default="capture_{seq:03d}.png",
    ),
    field("capture_count", "캡처 횟수 (0=무한)", "int", min=0, max=100000, default=10),
    field("interval_ms", "캡처 간격(ms)", "int", min=0, max=600000, default=1000),
    field("roi_x", "ROI X (0=전체)", "int", min=0, max=100000, default=0),
    field("roi_y", "ROI Y (0=전체)", "int", min=0, max=100000, default=0),
    field("roi_w", "ROI W (0=전체)", "int", min=0, max=100000, default=0),
    field("roi_h", "ROI H (0=전체)", "int", min=0, max=100000, default=0),
]

add_template(
    "periodic_screenshot_capture",
    "스크린샷 주기 저장",
    "지정 간격으로 스크린샷을 반복 저장합니다.",
    clone_fields(periodic_capture_fields),
    difficulty="intermediate",
    tags=["스크린샷", "주기", "반복"],
)

ocr_threshold_fields = [
    field("scenario_name", "시나리오 이름", default="OCR 값 기준 보호키"),
    field("variable_name", "저장 변수명", default="value"),
    field("ocr_roi_x", "OCR ROI X", "int", min=0, max=100000, default=0),
    field("ocr_roi_y", "OCR ROI Y", "int", min=0, max=100000, default=0),
    field("ocr_roi_w", "OCR ROI W", "int", min=1, max=100000, default=120),
    field("ocr_roi_h", "OCR ROI H", "int", min=1, max=100000, default=40),
    field("ocr_lang", "OCR 언어", default="eng"),
    field(
        "ocr_preprocess_mode",
        "OCR 전처리",
        "choice",
        options=OCR_PREPROCESS_OPTIONS,
        default="otsu",
    ),
    field("ocr_invert", "OCR 반전", "bool", default=False),
    field(
        "safe_operator",
        "안전 비교 연산",
        "choice",
        options=SAFE_OPERATOR_OPTIONS,
        default=">",
    ),
    field("threshold_value", "기준값", "float", default=50.0),
    field("guard_key", "실행할 보호키", default="f1"),
    field("guard_cooldown_ms", "보호키 후 대기(ms)", "int", min=0, max=600000, default=300),
]

add_template(
    "ocr_threshold_guard_key",
    "OCR 숫자 기준으로 보호키 실행",
    "OCR 값이 기준 미달일 때 보호키를 눌러 대응합니다.",
    clone_fields(ocr_threshold_fields),
    difficulty="advanced",
    tags=["OCR", "분기", "보호키"],
    prerequisites=["OCR 영역 좌표를 정확히 지정해야 합니다."],
    failure_points=["OCR 인식이 흔들리면 오탐 분기가 발생할 수 있습니다."],
)

ocr_store_fields = clone_fields(ocr_threshold_fields)
replace_field(ocr_store_fields, "safe_operator", field("safe_operator", "안전 비교 연산", default=">"))
replace_field(ocr_store_fields, "threshold_value", field("threshold_value", "기준값", "float", default=50.0))
replace_field(ocr_store_fields, "guard_key", field("guard_key", "실행할 보호키", default="f1"))
replace_field(
    ocr_store_fields,
    "guard_cooldown_ms",
    field("guard_cooldown_ms", "보호키 후 대기(ms)", "int", min=0, max=600000, default=300),
)
ocr_store_fields = [
    x
    for x in ocr_store_fields
    if x["name"] not in {"safe_operator", "threshold_value", "guard_key", "guard_cooldown_ms"}
]
set_default(ocr_store_fields, "scenario_name", "OCR 값 저장")
add_template(
    "ocr_store_only",
    "OCR 값만 변수로 저장",
    "OCR 결과를 변수에 저장하고 다음 스텝에서 활용합니다.",
    ocr_store_fields,
    difficulty="advanced",
    tags=["OCR", "변수"],
)

ocr_jump_fields = [
    field("scenario_name", "시나리오 이름", default="OCR 즉시 분기 보호키"),
    field("ocr_roi_x", "OCR ROI X", "int", min=0, max=100000, default=0),
    field("ocr_roi_y", "OCR ROI Y", "int", min=0, max=100000, default=0),
    field("ocr_roi_w", "OCR ROI W", "int", min=1, max=100000, default=120),
    field("ocr_roi_h", "OCR ROI H", "int", min=1, max=100000, default=40),
    field("ocr_lang", "OCR 언어", default="eng"),
    field(
        "ocr_preprocess_mode",
        "OCR 전처리",
        "choice",
        options=OCR_PREPROCESS_OPTIONS,
        default="otsu",
    ),
    field("ocr_invert", "OCR 반전", "bool", default=False),
    field(
        "condition_operator",
        "분기 비교 연산",
        "choice",
        options=CONDITION_OPERATOR_OPTIONS,
        default="<=",
    ),
    field("condition_value", "분기 기준값", "float", default=50.0),
    field("guard_key", "실행할 보호키", default="f1"),
    field("guard_cooldown_ms", "보호키 후 대기(ms)", "int", min=0, max=600000, default=300),
]

add_template(
    "ocr_jump_guard_key",
    "OCR 확인 후 바로 보호키 분기",
    "OCR 값 조건을 즉시 비교해 보호키 실행 여부를 결정합니다.",
    clone_fields(ocr_jump_fields),
    difficulty="advanced",
    tags=["OCR", "즉시분기", "보호키"],
)

pixel_guard_fields = [
    field("scenario_name", "시나리오 이름", default="픽셀 색상 기준 보호키"),
    field("pixel_x", "픽셀 X", "int", min=0, max=100000, default=0),
    field("pixel_y", "픽셀 Y", "int", min=0, max=100000, default=0),
    field("pixel_color_hex", "기대 색상(#RRGGBB)", default="#FFFFFF"),
    field("pixel_color_tolerance", "색상 허용 오차", "int", min=0, max=255, default=10),
    field("guard_key", "실행할 보호키", default="f1"),
    field("guard_cooldown_ms", "보호키 후 대기(ms)", "int", min=0, max=600000, default=300),
]

add_template(
    "pixel_guard_key",
    "픽셀 색상 기준으로 보호키 실행",
    "지정 색상이 아니면 보호키를 눌러 대응합니다.",
    clone_fields(pixel_guard_fields),
    difficulty="intermediate",
    tags=["픽셀검사", "분기", "보호키"],
)


# lineage-like MMORPG practical templates
lineage_click_attack_fields = clone_fields(click_hotkey_fields)
set_default(lineage_click_attack_fields, "scenario_name", "사냥 대상 클릭 후 공격")
set_default(lineage_click_attack_fields, "hotkey", "1")
set_default(lineage_click_attack_fields, "wait_ms", 80)
add_template(
    "lineage_click_attack",
    "사냥 대상 클릭 후 공격키",
    "지정 좌표를 클릭한 뒤 공격키를 눌러 전투를 시작합니다.",
    lineage_click_attack_fields,
    difficulty="beginner",
    tags=["리니지류", "게임", "사냥", "공격"],
    builder="click_then_hotkey",
)

lineage_loot_fields = clone_fields(hotkey_repeat_fields)
set_default(lineage_loot_fields, "scenario_name", "아이템 줍기 반복")
set_default(lineage_loot_fields, "hotkey", "f")
set_default(lineage_loot_fields, "repeat_count", 0)
set_default(lineage_loot_fields, "interval_ms", 250)
add_template(
    "lineage_loot_repeat",
    "아이템 줍기 키 반복",
    "줍기 키를 반복 입력해 드랍 아이템을 자동으로 습득합니다.",
    lineage_loot_fields,
    difficulty="beginner",
    tags=["리니지류", "게임", "루팅", "반복"],
    builder="hotkey_repeat",
)

lineage_tab_target_fields = clone_fields(hotkey_repeat_fields)
set_default(lineage_tab_target_fields, "scenario_name", "탭 타겟 반복")
set_default(lineage_tab_target_fields, "hotkey", "tab")
set_default(lineage_tab_target_fields, "repeat_count", 0)
set_default(lineage_tab_target_fields, "interval_ms", 300)
add_template(
    "lineage_tab_target_repeat",
    "탭 타겟 반복 전환",
    "탭 타겟 키를 반복해 주변 대상을 순차 선택합니다.",
    lineage_tab_target_fields,
    difficulty="beginner",
    tags=["리니지류", "게임", "타겟", "전환"],
    builder="hotkey_repeat",
)

lineage_npc_dialog_fields = clone_fields(hotkey_repeat_fields)
set_default(lineage_npc_dialog_fields, "scenario_name", "NPC 대화 넘기기")
set_default(lineage_npc_dialog_fields, "hotkey", "enter")
set_default(lineage_npc_dialog_fields, "repeat_count", 30)
set_default(lineage_npc_dialog_fields, "interval_ms", 120)
add_template(
    "lineage_npc_dialog_skip",
    "NPC 대화 넘기기 반복",
    "엔터 입력을 빠르게 반복해 대화/확인 창을 넘깁니다.",
    lineage_npc_dialog_fields,
    difficulty="beginner",
    tags=["리니지류", "게임", "NPC", "대화"],
    builder="hotkey_repeat",
)

lineage_attack_hold_fields = clone_fields(key_hold_fields)
set_default(lineage_attack_hold_fields, "scenario_name", "기본 공격 길게 누르기")
set_default(lineage_attack_hold_fields, "hotkey", "space")
set_default(lineage_attack_hold_fields, "hold_ms", 900)
set_default(lineage_attack_hold_fields, "repeat_count", 0)
set_default(lineage_attack_hold_fields, "interval_ms", 150)
add_template(
    "lineage_basic_attack_hold",
    "기본 공격 길게 누르기 반복",
    "기본 공격 키를 길게 누르는 패턴을 반복 실행합니다.",
    lineage_attack_hold_fields,
    difficulty="intermediate",
    tags=["리니지류", "게임", "공격", "키유지"],
    builder="key_hold_repeat",
)

lineage_buff_cycle_fields = clone_fields(wait_hotkey_fields)
set_default(lineage_buff_cycle_fields, "scenario_name", "버프 주기 갱신")
set_default(lineage_buff_cycle_fields, "repeat_count", 0)
set_default(lineage_buff_cycle_fields, "wait_ms", 180000)
set_default(lineage_buff_cycle_fields, "hotkey", "f5")
set_default(lineage_buff_cycle_fields, "post_wait_ms", 100)
add_template(
    "lineage_buff_cycle",
    "버프 스킬 주기 갱신",
    "지정 주기마다 버프 키를 눌러 버프를 유지합니다.",
    lineage_buff_cycle_fields,
    difficulty="intermediate",
    tags=["리니지류", "게임", "버프", "주기"],
    builder="wait_hotkey_repeat",
)

lineage_hp_potion_fields = clone_fields(ocr_threshold_fields)
set_default(lineage_hp_potion_fields, "scenario_name", "체력 낮으면 물약")
set_default(lineage_hp_potion_fields, "variable_name", "hp")
set_default(lineage_hp_potion_fields, "safe_operator", ">=")
set_default(lineage_hp_potion_fields, "threshold_value", 35.0)
set_default(lineage_hp_potion_fields, "guard_key", "1")
set_default(lineage_hp_potion_fields, "guard_cooldown_ms", 500)
add_template(
    "lineage_hp_potion_ocr",
    "체력 낮을 때 물약키",
    "OCR로 체력 숫자를 읽어 임계값 미만일 때 물약 키를 실행합니다.",
    lineage_hp_potion_fields,
    difficulty="advanced",
    tags=["리니지류", "게임", "체력", "물약", "OCR"],
    builder="ocr_threshold_guard_key",
)

lineage_mp_potion_fields = clone_fields(ocr_threshold_fields)
set_default(lineage_mp_potion_fields, "scenario_name", "마나 낮으면 물약")
set_default(lineage_mp_potion_fields, "variable_name", "mp")
set_default(lineage_mp_potion_fields, "safe_operator", ">=")
set_default(lineage_mp_potion_fields, "threshold_value", 25.0)
set_default(lineage_mp_potion_fields, "guard_key", "2")
set_default(lineage_mp_potion_fields, "guard_cooldown_ms", 500)
add_template(
    "lineage_mp_potion_ocr",
    "마나 낮을 때 물약키",
    "OCR로 마나 숫자를 읽어 임계값 미만일 때 물약 키를 실행합니다.",
    lineage_mp_potion_fields,
    difficulty="advanced",
    tags=["리니지류", "게임", "마나", "물약", "OCR"],
    builder="ocr_threshold_guard_key",
)

lineage_hp_return_fields = clone_fields(ocr_jump_fields)
set_default(lineage_hp_return_fields, "scenario_name", "체력 위험 시 귀환")
set_default(lineage_hp_return_fields, "condition_operator", ">")
set_default(lineage_hp_return_fields, "condition_value", 20.0)
set_default(lineage_hp_return_fields, "guard_key", "8")
set_default(lineage_hp_return_fields, "guard_cooldown_ms", 1000)
add_template(
    "lineage_hp_return_ocr",
    "체력 위험 시 귀환키",
    "체력이 위험 구간이면 즉시 귀환 키를 실행합니다.",
    lineage_hp_return_fields,
    difficulty="advanced",
    tags=["리니지류", "게임", "체력", "귀환", "OCR"],
    builder="ocr_jump_guard_key",
)

lineage_patrol_fields = clone_fields(two_points_fields)
set_default(lineage_patrol_fields, "scenario_name", "사냥터 두 지점 순찰")
set_default(lineage_patrol_fields, "repeat_count", 0)
set_default(lineage_patrol_fields, "interval_ms", 500)
add_template(
    "lineage_patrol_two_spots",
    "사냥터 두 지점 순찰 클릭",
    "두 좌표를 번갈아 클릭해 지정 구역을 반복 순찰합니다.",
    lineage_patrol_fields,
    difficulty="intermediate",
    tags=["리니지류", "게임", "순찰", "사냥터"],
    builder="click_two_points_loop",
)

lineage_combo_submacro_fields = clone_fields(submacro_retry_fields)
set_default(lineage_combo_submacro_fields, "scenario_name", "전투 콤보 서브매크로 반복")
set_default(lineage_combo_submacro_fields, "retry_count", 0)
set_default(lineage_combo_submacro_fields, "retry_interval_ms", 100)
add_template(
    "lineage_combo_submacro_loop",
    "전투 콤보 서브매크로 반복",
    "전투 콤보 매크로를 끊김 없이 반복 실행합니다.",
    lineage_combo_submacro_fields,
    difficulty="advanced",
    tags=["리니지류", "게임", "콤보", "서브매크로"],
    builder="submacro_retry_loop",
)

lineage_capture_fields = clone_fields(periodic_capture_fields)
set_default(lineage_capture_fields, "scenario_name", "사냥 기록 주기 캡처")
set_default(lineage_capture_fields, "save_path_pattern", "lineage_hunt_{seq:04d}.png")
set_default(lineage_capture_fields, "capture_count", 0)
set_default(lineage_capture_fields, "interval_ms", 30000)
add_template(
    "lineage_hunt_capture",
    "사냥 기록 주기 캡처",
    "사냥 중 화면을 주기적으로 저장해 장애 원인 추적에 사용합니다.",
    lineage_capture_fields,
    difficulty="intermediate",
    tags=["리니지류", "게임", "캡처", "로그"],
    builder="periodic_screenshot_capture",
)


catalog = {
    "schema_version": 1,
    "templates": TEMPLATES,
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(
    json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print(f"wrote {OUT_PATH} with {len(TEMPLATES)} templates")
