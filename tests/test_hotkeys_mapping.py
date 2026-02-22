from app.ui.hotkeys import SystemHotkeys


class _DummyMainWindow:
    _hk_run = ""
    _hk_stop = ""
    _hk_record = ""

    def winId(self):
        return 0


def test_get_vk_alias_mapping():
    hk = SystemHotkeys(_DummyMainWindow())
    assert hk._get_vk("pageup") == 0x21
    assert hk._get_vk("pagedown") == 0x22
    assert hk._get_vk("insert") == 0x2D
    assert hk._get_vk("delete") == 0x2E
    assert hk._get_vk("escape") == 0x1B


def test_parse_combo_invalid_returns_none_vk():
    hk = SystemHotkeys(_DummyMainWindow())
    assert hk._parse_combo("ctrl+")[1] is None
    assert hk._parse_combo("ctrl+notakey")[1] is None


def test_get_vk_extended_mapping():
    hk = SystemHotkeys(_DummyMainWindow())
    assert hk._get_vk("f24") == 0x87
    assert hk._get_vk("f0") is None
    assert hk._get_vk("f25") is None
    assert hk._get_vk("num0") == 0x60
    assert hk._get_vk("numpad9") == 0x69
    assert hk._get_vk("num_div") == 0x6F
    assert hk._get_vk("semicolon") == 0xBA
    assert hk._get_vk("minus") == 0xBD


def test_parse_combo_allows_any_order_and_spaces():
    hk = SystemHotkeys(_DummyMainWindow())
    mods, vk = hk._parse_combo("  f2 + ctrl + shift ")
    assert mods == (0x0002 | 0x0004)
    assert vk == 0x71


def test_parse_combo_rejects_multiple_key_tokens():
    hk = SystemHotkeys(_DummyMainWindow())
    assert hk._parse_combo("ctrl+a+b")[1] is None
