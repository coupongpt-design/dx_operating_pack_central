from app.core.template_processor import TemplateProcessor


def test_template_processor_renders_single_and_double_brace_tokens():
    out = TemplateProcessor.render("A={name}, B={{level}}", {"name": "Alice", "level": 10})
    assert out == "A=Alice, B=10"


def test_template_processor_keeps_unknown_tokens_and_reports_unresolved():
    out = TemplateProcessor.render("{{missing}} / {known}", {"known": "ok"})
    assert out == "{{missing}} / ok"
    assert TemplateProcessor.has_unresolved_placeholder(out) is True
