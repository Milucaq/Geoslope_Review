"""Tema visual de las pantallas de acceso (clave de instalación, administrador, login y 2FA).

Solo usa la paleta de GeoSlope Review y fuentes del sistema, por lo que funciona sin internet.
"""

import math
from urllib.parse import quote

BG = "#071B2B"
PRIMARY = "#167D8D"
SECONDARY = "#B9E4E8"
NEUTRAL = "#EEEEEE"


def _flat(html: str) -> str:
    """Quita sangrías y líneas vacías: Markdown corta el bloque HTML en la primera línea en blanco."""
    return "\n".join(line.strip() for line in html.splitlines() if line.strip())


def _mix(a: str, b: str, t: float) -> str:
    """Mezcla dos colores hex; t=0 devuelve a y t=1 devuelve b."""
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))


# --------------------------------------------------------------------------- ilustración


def _pit_svg() -> str:
    """Mina a tajo abierto con bancos (taludes) en estilo semi-plano, más capas de visión computacional."""
    rings , points = [], [], []
    n = 8
    for i in range(n):
        rx, ry, cy = 600 - 66 * i, 250 - 28 * i, 430 + 26 * i
        fill = _mix(BG, PRIMARY, max(0.08, 0.60 - 0.075 * i + (0.07 if i % 2 else 0)))
        rings.append(
            f'<ellipse cx="600" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}"/>'
            f'<ellipse cx="600" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#gsWall)"/>'
            f'<ellipse cx="600" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" '
            f'stroke="{SECONDARY}" stroke-opacity="{0.42 - 0.03 * i:.2f}" stroke-width="1.2"/>'
        )
    # prismas de monitoreo sobre los bancos
    for ring, deg in ((1, 200), (1, 335), (2, 262), (3, 175), (3, 318), (4, 235), (5, 300), (5, 150)):
        rx, ry, cy = 600 - 66 * ring, 250 - 28 * ring, 430 + 26 * ring
        a = math.radians(deg)
        points.append((round(600 + rx * math.cos(a)), round(cy + ry * math.sin(a))))
    prisms = "".join(
        f'<circle class="gs-halo" cx="{x}" cy="{y}" r="9" fill="{SECONDARY}" fill-opacity=".16" style="animation-delay:{(k * 0.55) % 3:.2f}s"/>'
        f'<path d="M{x} {y - 6}l5 6-5 6-5-6z" fill="{SECONDARY}"/>'
        for k, (x, y) in enumerate(points)
    )
    mesh = " ".join(f"{x},{y}" for x, y in (points[0], points[3], points[5], points[2], points[4], points[1]))
    mesh2 = " ".join(f"{x},{y}" for x, y in (points[0], points[7], points[6], points[1]))
    bx, by = points[4]
    brackets = (
        f'<g stroke="{SECONDARY}" stroke-width="2" fill="none" stroke-linecap="round" class="gs-bracket">'
        f'<path d="M{bx - 46} {by - 22}v-14h14M{bx + 32} {by - 36}h14v14M{bx + 46} {by + 22}v14h-14M{bx - 32} {by + 36}h-14v-14"/></g>'
    )
    return f"""<svg class="gs-art" viewBox="0 0 1200 1000" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Ilustración de una mina a tajo abierto con taludes escalonados y marcadores de monitoreo">
<defs>
<linearGradient id="gsSky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset=".55" stop-color="{_mix(BG, PRIMARY, .18)}"/><stop offset="1" stop-color="{_mix(BG, PRIMARY, .35)}"/></linearGradient>
<radialGradient id="gsGlow" cx=".72" cy=".16" r=".6"><stop offset="0" stop-color="{SECONDARY}" stop-opacity=".30"/><stop offset=".45" stop-color="{PRIMARY}" stop-opacity=".18"/><stop offset="1" stop-color="{PRIMARY}" stop-opacity="0"/></radialGradient>
<linearGradient id="gsWall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{SECONDARY}" stop-opacity=".22"/><stop offset=".45" stop-color="{SECONDARY}" stop-opacity="0"/><stop offset="1" stop-color="{BG}" stop-opacity=".25"/></linearGradient>
<linearGradient id="gsGround" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_mix(BG, PRIMARY, .50)}" stop-opacity="0"/><stop offset=".22" stop-color="{_mix(BG, PRIMARY, .50)}"/><stop offset="1" stop-color="{BG}"/></linearGradient>
<linearGradient id="gsRidgeA" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PRIMARY}" stop-opacity=".45"/><stop offset="1" stop-color="{BG}" stop-opacity=".1"/></linearGradient>
<linearGradient id="gsRidgeB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{SECONDARY}" stop-opacity=".16"/><stop offset="1" stop-color="{BG}" stop-opacity=".05"/></linearGradient>
<linearGradient id="gsBeam" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{SECONDARY}" stop-opacity=".20"/><stop offset="1" stop-color="{SECONDARY}" stop-opacity="0"/></linearGradient>
<radialGradient id="gsFloor" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{SECONDARY}" stop-opacity=".55"/><stop offset=".5" stop-color="{PRIMARY}" stop-opacity=".35"/><stop offset="1" stop-color="{PRIMARY}" stop-opacity="0"/></radialGradient>
<linearGradient id="gsScan" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{SECONDARY}" stop-opacity="0"/><stop offset=".85" stop-color="{SECONDARY}" stop-opacity=".16"/><stop offset="1" stop-color="{SECONDARY}" stop-opacity=".55"/></linearGradient>
<filter id="gsBlur" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="28"/></filter>
<clipPath id="gsPit"><ellipse cx="600" cy="430" rx="600" ry="250"/></clipPath>
</defs>
<rect width="1200" height="1000" fill="url(#gsSky)"/>
<rect width="1200" height="1000" fill="url(#gsGlow)"/>
<path d="M0 250 C90 200 170 150 270 190 C360 225 420 130 520 120 C640 108 700 190 800 160 C900 130 990 205 1200 150 V420 H0Z" fill="url(#gsRidgeB)"/>
<path d="M0 300 C120 240 200 230 310 262 C420 295 520 215 640 235 C760 255 850 205 960 230 C1060 252 1130 220 1200 236 V460 H0Z" fill="url(#gsRidgeA)"/>
<path d="M170 0H300L640 700H330Z" fill="url(#gsBeam)" opacity=".7"/>
<rect y="200" width="1200" height="800" fill="url(#gsGround)"/>
{''.join(rings)}
<ellipse cx="600" cy="640" rx="190" ry="66" fill="url(#gsFloor)"/>
<g clip-path="url(#gsPit)"><rect class="gs-scan" x="-200" y="150" width="200" height="560" fill="url(#gsScan)"/></g>
<g fill="none" stroke="{SECONDARY}" stroke-opacity=".45" stroke-width="1.2" stroke-dasharray="5 7" stroke-linejoin="round">
<polyline class="gs-dash" points="{mesh}"/>
<polyline class="gs-dash" points="{mesh2}" stroke-opacity=".3"/>
</g>
{brackets}
{prisms}
<g filter="url(#gsBlur)" fill="{SECONDARY}">
<ellipse class="gs-fog gs-fog-a" cx="330" cy="560" rx="420" ry="46" fill-opacity=".13"/>
<ellipse class="gs-fog gs-fog-b" cx="880" cy="700" rx="460" ry="52" fill-opacity=".11"/>
<ellipse class="gs-fog gs-fog-a" cx="560" cy="880" rx="640" ry="70" fill-opacity=".10"/>
<ellipse class="gs-fog gs-fog-b" cx="600" cy="230" rx="560" ry="34" fill-opacity=".09"/>
</g>
</svg>"""


def _particles(count: int = 18) -> str:
    spans = []
    for i in range(count):
        x = 6 + (math.sin(i * 12.9898) * 43758.5453 % 1) * 88
        y = 8 + (math.sin(i * 78.233) * 12345.678 % 1) * 84
        size = 2 + (i % 4)
        dur = 14 + (i * 3) % 13
        delay = -((i * 2.3) % dur)
        spans.append(
            f'<i style="left:{x:.1f}%;top:{y:.1f}%;width:{size}px;height:{size}px;'
            f'animation-duration:{dur}s;animation-delay:{delay:.1f}s"></i>'
        )
    return '<div class="gs-particles" aria-hidden="true">' + "".join(spans) + "</div>"


# --------------------------------------------------------------------------- HTML


def hero_html() -> str:
    return _flat(
        f"""<div class="gs-hero">
{_pit_svg()}
{_particles()}
<div class="gs-hero-copy">
<h2>Monitoreo inteligente de taludes</h2>
<p>Revisión geotécnica asistida por análisis cinemático y visión computacional para operaciones a tajo abierto.</p>
</div>
<div class="gs-hero-note">Las anomalías requieren revisión geotécnica y no constituyen predicciones de falla.</div>
</div>"""
    )


def header_html(brand: str, title: str, subtitle: str) -> str:
    mark = (
        f'<svg viewBox="0 0 32 32" width="34" height="34" aria-hidden="true">'
        f'<defs><linearGradient id="gsMark" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PRIMARY}"/><stop offset="1" stop-color="{SECONDARY}"/></linearGradient></defs>'
        f'<rect width="32" height="32" rx="9" fill="url(#gsMark)"/>'
        f'<path d="M6 11h20M9 16h14M12 21h8" stroke="{BG}" stroke-width="2.4" stroke-linecap="round"/></svg>'
    )
    return _flat(
        f"""<div class="gs-head">
<div class="gs-brand">{mark}<span>{brand}</span></div>
<h1>{title}</h1>
<p>{subtitle}</p>
<span class="gs-pill"><b></b>Sistema local offline</span>
</div>"""
    )


# --------------------------------------------------------------------------- CSS


def _icon(paths: str) -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='#B9E4E8' "
        f"stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>{paths}</svg>"
    )
    encoded = quote(svg, safe="/:=' ")
    return 'url("data:image/svg+xml,' + encoded + '")'


_USER = "<circle cx='12' cy='8' r='4'/><path d='M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7'/>"
_LOCK = "<rect x='4' y='10' width='16' height='11' rx='3'/><path d='M8 10V7a4 4 0 0 1 8 0v3'/>"
_SHIELD = "<path d='M12 3l8 3v6c0 5-3.4 8.2-8 9-4.6-.8-8-4-8-9V6z'/><path d='M9 12l2 2 4-4'/>"
_KEY = "<circle cx='8' cy='15' r='4'/><path d='M11 12l9-9M16 7l3 3'/>"

# clave de widget -> icono inicial del campo
_ICONS = {
    "login_username": _USER,
    "setup_username": _USER,
    "setup_name": _USER,
    "login_password": _LOCK,
    "setup_password": _LOCK,
    "setup_repeat": _LOCK,
    "setup_key": _KEY,
    "otp_code": _SHIELD,
}

_CSS = """
:root{--gs-bg:__BG__;--gs-primary:__PRIMARY__;--gs-secondary:__SECONDARY__;--gs-neutral:__NEUTRAL__}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],footer{display:none!important}
.stApp{background:var(--gs-bg)!important}
.stApp [data-testid="stMainBlockContainer"],.stApp .block-container{padding:0!important;max-width:100%!important}
.st-key-gs_login_root{min-height:100vh;color:var(--gs-neutral);font-family:"Segoe UI Variable Display","Segoe UI Variable","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
background:radial-gradient(900px 600px at 88% 8%,rgba(22,125,141,.22),transparent 60%),var(--gs-bg)}
.st-key-gs_login_root [data-testid="stHorizontalBlock"]{gap:0!important;align-items:stretch!important;min-height:100vh}
.st-key-gs_login_root [data-testid="stColumn"],.st-key-gs_login_root [data-testid="column"]{min-width:0}
.st-key-gs_login_root [data-testid="stColumn"]:first-child [data-testid="stVerticalBlock"],
.st-key-gs_login_root [data-testid="column"]:first-child [data-testid="stVerticalBlock"]{gap:0!important}
.st-key-gs_login_root [data-testid="stColumn"]:last-child>[data-testid="stVerticalBlock"],
.st-key-gs_login_root [data-testid="column"]:last-child>[data-testid="stVerticalBlock"]{min-height:100vh;justify-content:center;padding:2rem clamp(1.25rem,4vw,3.5rem)}

/* ---------- hero ---------- */
.gs-hero{position:relative;height:100vh;min-height:560px;overflow:hidden;background:var(--gs-bg);animation:gs-fade 1.2s ease both}
.gs-hero::after{content:"";position:absolute;inset:0;pointer-events:none;
background:linear-gradient(90deg,transparent 78%,var(--gs-bg) 100%),linear-gradient(0deg,rgba(7,27,43,.92) 0%,rgba(7,27,43,0) 34%),linear-gradient(180deg,rgba(7,27,43,.65) 0%,rgba(7,27,43,0) 30%)}
.gs-art{position:absolute;inset:0;width:100%;height:100%;display:block}
.gs-hero-copy{position:absolute;z-index:2;left:clamp(1.5rem,5vw,4.5rem);top:clamp(2rem,9vh,5.5rem);max-width:30rem}
.gs-hero-copy h2{margin:0;font-size:clamp(1.9rem,3.2vw,3rem);line-height:1.08;letter-spacing:-.025em;font-weight:700;color:var(--gs-neutral)}
.gs-hero-copy p{margin:1rem 0 0;font-size:1.02rem;line-height:1.55;color:rgba(238,238,238,.78);max-width:26rem}
.gs-hero-note{position:absolute;z-index:2;left:clamp(1.5rem,5vw,4.5rem);right:3rem;bottom:2rem;font-size:.84rem;line-height:1.5;color:rgba(238,238,238,.72)}
.gs-particles{position:absolute;inset:0;pointer-events:none;z-index:1}
.gs-particles i{position:absolute;border-radius:50%;background:var(--gs-secondary);opacity:0;animation:gs-float linear infinite}
.gs-halo{transform-box:fill-box;transform-origin:center;animation:gs-pulse 3.2s ease-in-out infinite}
.gs-scan{animation:gs-scan 8s cubic-bezier(.45,.05,.4,.95) infinite}
.gs-fog-a{animation:gs-drift 26s ease-in-out infinite alternate}
.gs-fog-b{animation:gs-drift 32s ease-in-out infinite alternate-reverse}
.gs-dash{animation:gs-dash 30s linear infinite}
.gs-bracket{animation:gs-blink 4.5s ease-in-out infinite}

/* ---------- tarjeta ---------- */
.st-key-gs_login_card{position:relative;width:100%;max-width:27rem;margin:0 auto;padding:2.25rem 2.25rem 2rem;border-radius:20px;
background:linear-gradient(160deg,rgba(185,228,232,.10),rgba(185,228,232,.03));
border:1px solid rgba(185,228,232,.18);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);
box-shadow:0 24px 60px rgba(0,0,0,.40),0 0 0 1px rgba(22,125,141,.10),inset 0 1px 0 rgba(238,238,238,.08);
animation:gs-rise .8s cubic-bezier(.2,.7,.2,1) both}
.st-key-gs_login_card::before{content:"";position:absolute;inset:-1px;border-radius:20px;padding:1px;pointer-events:none;
background:linear-gradient(135deg,rgba(185,228,232,.5),rgba(22,125,141,0) 40%,rgba(22,125,141,.4));
-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude}
.st-key-gs_login_card [data-testid="stVerticalBlock"]{gap:1rem}
.gs-head{margin-bottom:.5rem}
.gs-brand{display:flex;align-items:center;gap:.7rem;font-weight:600;font-size:1rem;color:var(--gs-neutral);margin-bottom:1.6rem}
.gs-head h1{margin:0;padding:0;font-size:2.2rem;line-height:1.1;letter-spacing:-.03em;font-weight:750;color:var(--gs-neutral)}
.gs-head p{margin:.7rem 0 1rem;font-size:.97rem;line-height:1.5;color:rgba(238,238,238,.76)}
.gs-pill{display:inline-flex;align-items:center;gap:.5rem;padding:.3rem .75rem;border-radius:999px;font-size:.8rem;color:var(--gs-secondary);
background:rgba(22,125,141,.18);border:1px solid rgba(185,228,232,.22)}
.gs-pill b{width:7px;height:7px;border-radius:50%;background:var(--gs-secondary);box-shadow:0 0 0 0 rgba(185,228,232,.6);animation:gs-ping 2.6s ease-out infinite}

/* ---------- campos ---------- */
.st-key-gs_login_root [data-testid="stWidgetLabel"] p,.st-key-gs_login_root label p{color:var(--gs-neutral)!important;font-size:.88rem;font-weight:550}
.st-key-gs_login_root [data-baseweb="input"]{background-color:rgba(238,238,238,.05)!important;border:1px solid rgba(185,228,232,.24)!important;border-radius:14px!important;
min-height:3rem;transition:border-color .2s ease,box-shadow .2s ease,background-color .2s ease;background-repeat:no-repeat;background-position:14px center;background-size:20px}
.st-key-gs_login_root [data-baseweb="input"]:hover{border-color:rgba(185,228,232,.45)!important}
.st-key-gs_login_root [data-baseweb="input"]:focus-within{border-color:var(--gs-secondary)!important;background-color:rgba(22,125,141,.14)!important;box-shadow:0 0 0 4px rgba(22,125,141,.32),0 0 24px rgba(22,125,141,.28)}
.st-key-gs_login_root [data-baseweb="base-input"]{background:transparent!important;border-radius:14px}
.st-key-gs_login_root [data-baseweb="input"] input{color:var(--gs-neutral)!important;-webkit-text-fill-color:var(--gs-neutral);padding-left:2.75rem!important;font-size:.98rem}
.st-key-gs_login_root [data-baseweb="input"] input::placeholder{color:rgba(238,238,238,.5)!important;-webkit-text-fill-color:rgba(238,238,238,.5)}
.st-key-gs_login_root [data-baseweb="input"] button{color:var(--gs-secondary)!important;background:transparent!important}
.st-key-gs_login_root [data-testid="stForm"]{border:0!important;padding:0!important;background:transparent!important}
.st-key-gs_login_root [data-testid="stCaptionContainer"],.st-key-gs_login_root [data-testid="stCaptionContainer"] p{color:rgba(238,238,238,.68)!important;font-size:.82rem}
.st-key-gs_login_root [data-testid="stMarkdownContainer"] p{color:rgba(238,238,238,.82)}
.st-key-gs_login_root [data-testid="stCheckbox"] label{color:var(--gs-neutral)}
.st-key-gs_login_root [data-testid="stCheckbox"] [data-baseweb="checkbox"]>div:first-child{border-radius:6px;border-color:rgba(185,228,232,.5)}

/* ---------- botones ---------- */
.st-key-gs_login_root button[kind="primary"],.st-key-gs_login_root button[kind="primaryFormSubmit"],
.st-key-gs_login_root [data-testid="stBaseButton-primary"],.st-key-gs_login_root [data-testid="stBaseButton-primaryFormSubmit"]{
width:100%;min-height:3rem;border:0!important;border-radius:14px!important;font-weight:700;font-size:1rem;letter-spacing:.01em;
color:var(--gs-bg)!important;background:linear-gradient(110deg,var(--gs-primary),var(--gs-secondary),var(--gs-primary))!important;background-size:220% 100%!important;background-position:0% 0;
box-shadow:0 10px 26px rgba(0,0,0,.35),0 0 0 rgba(22,125,141,0);transition:background-position .6s ease,box-shadow .25s ease,transform .12s ease}
.st-key-gs_login_root button[kind="primary"]:hover,.st-key-gs_login_root button[kind="primaryFormSubmit"]:hover,
.st-key-gs_login_root [data-testid="stBaseButton-primary"]:hover,.st-key-gs_login_root [data-testid="stBaseButton-primaryFormSubmit"]:hover{
background-position:100% 0;box-shadow:0 12px 30px rgba(0,0,0,.35),0 0 28px rgba(22,125,141,.55);transform:translateY(-1px)}
.st-key-gs_login_root button[kind="primary"]:active,.st-key-gs_login_root button[kind="primaryFormSubmit"]:active,
.st-key-gs_login_root [data-testid="stBaseButton-primary"]:active,.st-key-gs_login_root [data-testid="stBaseButton-primaryFormSubmit"]:active{transform:scale(.98)}
.st-key-gs_login_root button:focus-visible{outline:3px solid var(--gs-secondary)!important;outline-offset:3px}
.st-key-gs_login_root button[kind="secondary"],.st-key-gs_login_root [data-testid="stBaseButton-secondary"]{
border-radius:14px!important;background:transparent!important;color:var(--gs-secondary)!important;border:1px solid rgba(185,228,232,.32)!important;transition:background .2s ease,box-shadow .2s ease}
.st-key-gs_login_root button[kind="secondary"]:hover,.st-key-gs_login_root [data-testid="stBaseButton-secondary"]:hover{background:rgba(22,125,141,.22)!important;box-shadow:0 0 18px rgba(22,125,141,.35)}

/* ---------- avisos, QR, expander ---------- */
.st-key-gs_login_root [data-testid="stAlert"]{border-radius:14px;background:rgba(22,125,141,.16)!important;border:1px solid rgba(185,228,232,.28);color:var(--gs-neutral)}
.st-key-gs_login_root [data-testid="stAlert"] *{color:var(--gs-neutral)!important}
.st-key-gs_login_root [data-testid="stImage"] img{border-radius:14px;background:var(--gs-neutral);padding:10px}
.st-key-gs_login_root [data-testid="stExpander"]{border:1px solid rgba(185,228,232,.22)!important;border-radius:14px!important;background:rgba(238,238,238,.03)}
.st-key-gs_login_root [data-testid="stExpander"] summary,.st-key-gs_login_root [data-testid="stExpander"] summary p{color:var(--gs-neutral)!important}
.gs-hint{margin:.25rem 0 0;font-size:.84rem;line-height:1.5;color:rgba(238,238,238,.68)}

/* ---------- animaciones ---------- */
@keyframes gs-fade{from{opacity:0}to{opacity:1}}
@keyframes gs-rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@keyframes gs-float{0%{opacity:0;transform:translate3d(0,14px,0)}20%{opacity:.7}80%{opacity:.5}100%{opacity:0;transform:translate3d(14px,-70px,0)}}
@keyframes gs-pulse{0%,100%{transform:scale(1);opacity:.9}50%{transform:scale(1.9);opacity:.2}}
@keyframes gs-scan{from{transform:translateX(0)}to{transform:translateX(1500px)}}
@keyframes gs-drift{from{transform:translateX(-50px)}to{transform:translateX(50px)}}
@keyframes gs-dash{to{stroke-dashoffset:-240}}
@keyframes gs-blink{0%,100%{opacity:.35}50%{opacity:1}}
@keyframes gs-ping{0%{box-shadow:0 0 0 0 rgba(185,228,232,.55)}80%,100%{box-shadow:0 0 0 9px rgba(185,228,232,0)}}

/* ---------- responsive ---------- */
@media (max-width:900px){
.st-key-gs_login_root [data-testid="stHorizontalBlock"]{flex-direction:column!important;min-height:0}
.st-key-gs_login_root [data-testid="stColumn"],.st-key-gs_login_root [data-testid="column"]{width:100%!important;flex:1 1 100%!important;min-width:100%!important}
.gs-hero{height:260px;min-height:0}
.gs-hero-copy{top:1.5rem}.gs-hero-copy p,.gs-hero-note{display:none}
.gs-hero-copy h2{font-size:1.6rem}
.st-key-gs_login_root [data-testid="stColumn"]:last-child>[data-testid="stVerticalBlock"],
.st-key-gs_login_root [data-testid="column"]:last-child>[data-testid="stVerticalBlock"]{min-height:0;padding:1.5rem 1.25rem 2.5rem;margin-top:-3rem}
.st-key-gs_login_card{padding:1.6rem 1.4rem}
.gs-head h1{font-size:1.8rem}
}
@media (prefers-reduced-motion:reduce){
.st-key-gs_login_root *,.st-key-gs_login_root *::before{animation:none!important;transition:none!important}
.gs-particles{display:none}
}
"""


def login_css() -> str:
    css = (
        _CSS.replace("__BG__", BG)
        .replace("__PRIMARY__", PRIMARY)
        .replace("__SECONDARY__", SECONDARY)
        .replace("__NEUTRAL__", NEUTRAL)
    )
    icons = "".join(
        f'.st-key-{key} [data-baseweb="input"]{{background-image:{_icon(paths)}}}'
        for key, paths in _ICONS.items()
    )
    return "<style>\n" + _flat(css + icons) + "\n</style>"
