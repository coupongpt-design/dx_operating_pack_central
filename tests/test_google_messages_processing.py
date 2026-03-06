from google_messages.google_messages_processing import GoogleMessagesProcessingMixin


class _FakeThumb:
    def __init__(self, src=None, *, visible=True, natural_widths=None, get_src_error=False):
        self.src = src
        self.visible = visible
        self.natural_widths = list(natural_widths or [])
        self.get_src_error = get_src_error
        self.scroll_calls = []
        self.evaluate_calls = 0

    def get_attribute(self, name):
        assert name == "src"
        if self.get_src_error:
            raise RuntimeError("src unavailable")
        return self.src

    def is_visible(self):
        return self.visible

    def scroll_into_view_if_needed(self, timeout=None):
        self.scroll_calls.append(timeout)

    def evaluate(self, script):
        assert script == "el => el.naturalWidth > 0"
        self.evaluate_calls += 1
        if self.natural_widths:
            return self.natural_widths.pop(0)
        return False


class _FakePage:
    def __init__(self):
        self.wait_calls = []

    def wait_for_timeout(self, timeout_ms):
        self.wait_calls.append(timeout_ms)


def test_collect_blob_image_candidates_filters_non_blob_and_errors():
    thumbs = [
        _FakeThumb("blob:one"),
        _FakeThumb("https://example.com/image.jpg"),
        _FakeThumb(None),
        _FakeThumb(get_src_error=True),
    ]

    candidates = GoogleMessagesProcessingMixin._collect_blob_image_candidates(thumbs, 7)

    assert len(candidates) == 1
    assert candidates[0][0] is thumbs[0]
    assert candidates[0][1] == "blob:one"


def test_prepare_blob_image_for_save_skips_scroll_for_hidden_images():
    page = _FakePage()
    thumb = _FakeThumb("blob:hidden", visible=False)

    GoogleMessagesProcessingMixin._prepare_blob_image_for_save(page, thumb, 3, 1)

    assert thumb.scroll_calls == []
    assert thumb.evaluate_calls == 0
    assert page.wait_calls == []


def test_prepare_blob_image_for_save_limits_wait_for_visible_images():
    page = _FakePage()
    thumb = _FakeThumb("blob:visible", visible=True, natural_widths=[False, False, True])

    GoogleMessagesProcessingMixin._prepare_blob_image_for_save(page, thumb, 5, 2)

    assert thumb.scroll_calls == [1500]
    assert thumb.evaluate_calls == 3
    assert page.wait_calls == [100, 100]
