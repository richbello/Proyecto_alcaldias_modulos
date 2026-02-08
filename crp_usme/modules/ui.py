# modules/ui.py
import os
import streamlit as st

BOGOTA_YELLOW = "#FCD116"
BOGOTA_RED = "#CE1126"


def inject_theme():
    """Tema institucional Bogotá con contraste correcto (texto negro)."""
    st.markdown(
        f"""
        <style>
        :root {{
          --bg-main: #F1F5F9;          /* gris claro institucional */
          --bg-card: #FFFFFF;
          --text-main: #0F172A;        /* TEXTO NEGRO */
          --muted: #334155;
          --border: #E2E8F0;

          --yellow: {BOGOTA_YELLOW};   /* Bogotá */
          --red: {BOGOTA_RED};
        }}

        /* ===== FONDO GENERAL ===== */
        .stApp {{
          background-color: var(--bg-main) !important;
          color: var(--text-main) !important;
        }}

        /* ===== TEXTO GLOBAL (FORZADO) ===== */
        html, body, div, span, p, label {{
          color: var(--text-main) !important;
        }}

        /* ===== HEADERS ===== */
        h1, h2, h3, h4 {{
          color: var(--text-main) !important;
          font-weight: 700;
        }}

        /* ===== SIDEBAR ===== */
        section[data-testid="stSidebar"] {{
          background-color: #FFFFFF !important;
          border-right: 4px solid var(--yellow);
        }}

        section[data-testid="stSidebar"] * {{
          color: var(--text-main) !important;
        }}

        /* ===== INPUTS (LOGIN) ===== */
        input, textarea, select {{
          background-color: #FFFFFF !important;
          color: var(--text-main) !important;
          border: 1px solid var(--border) !important;
        }}

        input::placeholder {{
          color: #64748B !important;
        }}

        /* ===== BOTONES ===== */
        button {{
          background-color: var(--red) !important;
          color: #FFFFFF !important;
          font-weight: 700;
          border-radius: 10px;
        }}

        button:hover {{
          background-color: #A50F1F !important;
          color: #FFFFFF !important;
        }}

        /* ===== TARJETAS ===== */
        .card {{
          background-color: var(--bg-card) !important;
          border: 1px solid var(--border);
          border-radius: 14px;
          color: var(--text-main) !important;
        }}

        /* ===== PILLS / BADGES ===== */
        .pill {{
          background-color: #F8FAFC;
          color: var(--text-main) !important;
          border: 1px solid var(--border);
        }}

        .pill-secure {{
          background-color: #FEF9C3;   /* amarillo suave */
          color: #854D0E !important;
          border-color: var(--yellow);
        }}

        .pill-warn {{
          background-color: #FEE2E2;   /* rojo suave */
          color: #7F1D1D !important;
          border-color: var(--red);
        }}

        /* ===== DATAFRAMES ===== */
        div[data-testid="stDataFrame"] {{
          background-color: #FFFFFF !important;
          color: var(--text-main) !important;
        }}

        /* ===== PROGRESS BAR ===== */
        div[role="progressbar"] > div {{
          background-color: var(--yellow) !important;
        }}

        /* ===== LIMPIEZA ===== */
        footer, header {{
          visibility: hidden;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def header_brand(assets_dir: str, usuario: str | None, role: str | None):
    """Header institucional con badge de rol."""

    # ---- determinar badge por rol ----
    role_txt = role or "-"
    role_badge = "pill"
    if role == "admin":
        role_badge = "pill-warn"
    elif role == "usuario":
        role_badge = "pill-secure"

    # ---- logo ----
    escudos = ["escudo.png", "escudo.jpg", "descarga.jpg"]
    logo = next(
        (os.path.join(assets_dir, e) for e in escudos if os.path.exists(os.path.join(assets_dir, e))),
        None,
    )

    left, right = st.columns([1, 4], vertical_alignment="center")

    with left:
        if logo:
            st.image(logo, width=90)
        else:
            st.markdown(
                f"""
                <div style="width:90px;height:90px;border-radius:18px;
                background:linear-gradient(180deg,{BOGOTA_YELLOW},{BOGOTA_RED});
                display:flex;align-items:center;justify-content:center;
                font-weight:900;color:#111;">
                USME
                </div>
                """,
                unsafe_allow_html=True,
            )

    with right:
        st.markdown(
            f"""
            <div class="hero">
              <div style="font-size:30px;font-weight:900;">Alcaldía Local de Usme</div>
              <div style="color:#475569;font-size:14px;">
                Generador seguro de Plantilla CRP — diseño minimalista con identidad Bogotá
              </div>

              <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;">
                <span class="pill pill-secure">🛡️ Seguridad</span>
                <span class="pill">📄 PDF → Excel</span>
                <span class="pill">🏛️ Bogotá</span>
              </div>

              <div style="margin-top:12px;display:flex;gap:10px;">
                <span class="pill">👤 {usuario if usuario else "No autenticado"}</span>
                <span class="pill {role_badge}">🔑 Rol: {role_txt}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def security_status_panel(attempts_left: int, auto_alerts: bool, locked: bool, session_left_s: int | None):
    status = "🔒 Bloqueado" if locked else "✅ Activo"
    pill_class = "pill-warn" if locked else "pill-secure"
    alerts_txt = "ON" if auto_alerts else "OFF"

    if session_left_s is None:
        session_txt = "—"
    else:
        session_txt = f"{session_left_s//60:02d}:{session_left_s%60:02d}"

    st.markdown(
        f"""
        <div class="card">
          <b>Ciberseguridad</b><br/>
          <span class="pill {pill_class}">{status}</span><br/><br/>
          Intentos restantes: <b>{attempts_left}</b><br/>
          Alertas: <b>{alerts_txt}</b><br/>
          Sesión restante: <b>{session_txt}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )