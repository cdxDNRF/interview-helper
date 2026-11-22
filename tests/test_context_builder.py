import pytest

from app.services.context_builder import (
    _truncate_to_token_budget,
    count_tokens_accurate,
    parse_resume_bytes,
    validate_github_repo_url,
)


def _build_minimal_pdf(text: str) -> bytes:
    """Create a minimal valid single-page PDF containing ASCII text for MarkItDown tests."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
        + stream
        + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_start = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return bytes(out)


def test_parse_markdown_resume():
    md, warnings = parse_resume_bytes("cv.md", "# 张三\n- 熟练掌握 FastAPI".encode("utf-8"))
    assert "张三" in md
    assert warnings == []


def test_parse_pdf_resume_via_markitdown():
    pdf_bytes = _build_minimal_pdf(
        "Senior FastAPI Backend Engineer Resume with LangGraph and SQLite WAL"
    )
    md, warnings = parse_resume_bytes("resume.pdf", pdf_bytes)
    assert "Senior FastAPI Backend Engineer Resume" in md
    assert len(warnings) == 0


def test_github_url_validation_rejects_injection():
    assert (
        validate_github_repo_url("https://github.com/cdxDNRF/interview-helper/")
        == "https://github.com/cdxDNRF/interview-helper"
    )
    with pytest.raises(ValueError):
        validate_github_repo_url("https://github.com/foo/bar; rm -rf /")
    with pytest.raises(ValueError):
        validate_github_repo_url("http://127.0.0.1:8000/secret")


def test_repomix_token_budget_enforced_under_20k():
    big_text = ("def handle_request(ctx): return ctx.user_id\n" * 4000)
    assert count_tokens_accurate(big_text) > 20000
    trimmed, final_tokens, truncated = _truncate_to_token_budget(big_text, 20000)
    assert truncated is True
    assert final_tokens <= 20000
    assert "Truncated by interview-helper" in trimmed
