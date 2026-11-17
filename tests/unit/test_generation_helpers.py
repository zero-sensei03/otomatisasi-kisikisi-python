from __future__ import annotations

import pytest

from app.services.generation_service import generation_error_title, generation_user_error, truncate_material


def test_material_character_limit_does_not_truncate_content_silently():
    assert truncate_material("materi", 6) == "materi"
    with pytest.raises(ValueError, match="melebihi batas"):
        truncate_material("materi tambahan", 6)


@pytest.mark.parametrize(
    ("message", "title"),
    [
        ("Autentikasi layanan AI gagal. Periksa API key.", "Autentikasi layanan AI gagal"),
        ("Kuota layanan AI tercapai.", "Kuota layanan AI tercapai"),
        ("Layanan AI mengalami timeout.", "Layanan AI mengalami timeout"),
        ("File sumber materi tidak ditemukan.", "Sumber materi bermasalah"),
        ("Respons AI tidak sesuai format.", "Hasil AI tidak valid"),
        ("Terjadi kegagalan saat menyimpan hasil generation.", "Penyimpanan generation gagal"),
    ],
)
def test_generation_error_title_is_selected_from_safe_user_message(message, title):
    assert generation_error_title(message) == title


def test_unclassified_generation_error_uses_safe_fallback_without_exception_detail():
    message = generation_user_error(RuntimeError("private SQL statement with token=hidden"))
    assert "Periksa materi" in message
    assert "private SQL" not in message
    assert "hidden" not in message


def test_generation_detail_offers_new_generation_without_retry_action():
    from pathlib import Path

    template = Path("app/templates/pages/generation/detail.html").read_text()
    assert 'href="/generation/create">Buat Generation Baru</a>' in template
    assert "Generate Ulang" not in template
    assert "Regenerate" not in template


def test_settings_form_accepts_one_billion_and_always_cleans_loading_state():
    from pathlib import Path

    template = Path("app/templates/pages/admin/settings/index.html").read_text()
    assert "'1000000000','generation.max_material_characters'" in template
    assert "label.textContent='Memproses…'" in template
    assert "finally{if(timeout)clearTimeout(timeout);isSubmitting=false;submit.disabled=false" in template
    assert "response.status===422" in template
    assert "catch(error){showGeneral(error.name==='AbortError'" in template
