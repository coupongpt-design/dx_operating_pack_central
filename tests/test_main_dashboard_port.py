from macro import main_refactored


def test_load_dashboard_port_returns_default_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(main_refactored, "_dashboard_port_file", lambda: tmp_path / "dashboard_port.txt")

    assert main_refactored._load_dashboard_port() == 5000


def test_load_dashboard_port_reads_saved_value(monkeypatch, tmp_path):
    port_file = tmp_path / "dashboard_port.txt"
    port_file.write_text("5007", encoding="utf-8")
    monkeypatch.setattr(main_refactored, "_dashboard_port_file", lambda: port_file)

    assert main_refactored._load_dashboard_port() == 5007


def test_save_dashboard_port_persists_value(monkeypatch, tmp_path):
    port_file = tmp_path / "nested" / "dashboard_port.txt"
    monkeypatch.setattr(main_refactored, "_dashboard_port_file", lambda: port_file)

    main_refactored._save_dashboard_port(5010)

    assert port_file.read_text(encoding="utf-8") == "5010"


def test_configure_dashboard_port_keeps_current_on_blank(monkeypatch):
    monkeypatch.setattr(main_refactored, "safe_input", lambda prompt: "")

    assert main_refactored._configure_dashboard_port(5000) == 5000


def test_configure_dashboard_port_accepts_valid_custom_port(monkeypatch):
    monkeypatch.setattr(main_refactored, "safe_input", lambda prompt: "5001")

    assert main_refactored._configure_dashboard_port(5000) == 5001


def test_resolve_dashboard_port_reprompts_when_default_port_is_busy(monkeypatch):
    prompts = []

    def fake_configure(port):
        prompts.append(port)
        return 5001

    def fake_available(port):
        return port == 5001

    monkeypatch.setattr(main_refactored, "_configure_dashboard_port", fake_configure)
    monkeypatch.setattr(main_refactored.dashboard, "is_port_available", fake_available)

    assert main_refactored._resolve_dashboard_port(5000, auto_mode=False) == 5001
    assert prompts == [5001]


def test_resolve_dashboard_port_auto_mode_uses_next_available_port(monkeypatch):
    monkeypatch.setattr(
        main_refactored.dashboard,
        "is_port_available",
        lambda port: port == 5002,
    )

    assert main_refactored._resolve_dashboard_port(5000, auto_mode=True) == 5002
