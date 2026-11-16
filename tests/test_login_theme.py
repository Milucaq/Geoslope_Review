"""Pruebas unitarias para el tema visual de autenticación y Cloud UI."""

from gsreview.presentation.login_theme import (
    _mix,
    _flat,
    _icon,
    _pit_svg,
    _particles,
    hero_html,
    header_html,
    login_css,
)


def test_login_theme_helpers_and_html_generation():
    assert _mix("#000000", "#FFFFFF", 0.5) == "#808080"
    assert _flat("  a  \n\n  b  ") == "a\nb"

    icon_url = _icon("<path d='M0 0'/>")
    assert icon_url.startswith("url(\"data:image/svg+xml,")

    svg = _pit_svg()
    assert "<svg" in svg and "gs-art" in svg

    particles = _particles(5)
    assert '<div class="gs-particles"' in particles

    hero = hero_html()
    assert 'class="gs-hero"' in hero
    assert "Monitoreo inteligente de taludes" in hero

    header = header_html("GeoSlope Review", "Iniciar sesión", "Introduce credenciales")
    assert "GeoSlope Review" in header
    assert "Iniciar sesión" in header

    css = login_css()
    assert ".st-key-gs_login_card" in css
