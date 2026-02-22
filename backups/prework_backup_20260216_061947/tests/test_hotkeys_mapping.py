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
