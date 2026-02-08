import os
import logging
from datetime import datetime

import streamlit as st
import pandas as pd

from modules.ui import inject_theme, header_brand, security_status_panel
from modules.auth import authenticate, login_guard, upsert_user, reset_users
from modules.security import LoginPolicy, now_ts
from modules.pdf_parser import extract_rows_from_pdf
from modules.transform import build_records, fixed_fields
from modules.reports import build_output_excel, build_audit_excel

# -----------------------
# Configuración
# -----------------------
st.set_page_config(page_title="Alcaldía Local de Usme", layout="wide")
inject_theme()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SALIDAS_DIR = os.path.join(BASE_DIR, "salidas")
LOG_DIR = os.path.join(BASE_DIR, "logs")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(SALIDAS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, "accesos.log")
ALERTS_LOG = os.path.join(LOG_DIR, "alerts.log")

logger = logging.getLogger("crp_usme")
logger.setLevel(logging.INFO)
if not any(
    isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == LOG_PATH
    for h in logger.handlers
):
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    logger.addHandler(fh)


def send_alert(message, level="info"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - ALERT - {level.upper()} - {message}\n"
    try:
        with open(ALERTS_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    logger.info(f"ALERTA: {message}")


# -----------------------
# Estado / Seguridad
# -----------------------
policy = LoginPolicy()

st.session_state.setdefault("usuario", None)
st.session_state.setdefault("role", None)
st.session_state.setdefault("attempts", 0)
st.session_state.setdefault("lock_until", 0.0)
st.session_state.setdefault("last_activity", 0.0)
st.session_state.setdefault("auto_alerts", False)

ok, msg = login_guard(st.session_state, policy)
if not ok and msg:
    st.warning(msg)

# -----------------------
# Header principal
# -----------------------
header_brand(ASSETS_DIR, st.session_state.get("usuario"), st.session_state.get("role"))
st.write("")


# -----------------------
# Sidebar: Login + Seguridad + Recuperación
# -----------------------
with st.sidebar:
    st.caption("🔎 Diagnóstico")
    st.code(os.path.abspath("data/users.json"))


with st.sidebar:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🔐 Acceso")
    st.caption("Login seguro con hash PBKDF2, bloqueo por intentos y auditoría.")

    if st.session_state.get("usuario") is None:
        u = st.text_input("Usuario", key="login_user")
        p = st.text_input("Clave", type="password", key="login_pass")

        if st.button("Ingresar"):
            if st.session_state.get("lock_until", 0.0) and now_ts() < st.session_state["lock_until"]:
                st.error("Cuenta bloqueada temporalmente.")
            else:
                success, role = authenticate((u or "").strip(), p or "")
                if success:
                    st.session_state["usuario"] = (u or "").strip()
                    st.session_state["role"] = role
                    st.session_state["attempts"] = 0
                    st.session_state["last_activity"] = now_ts()
                    logger.info(f"Login exitoso: {u} (role={role})")
                    st.rerun()
                else:
                    st.session_state["attempts"] = int(st.session_state.get("attempts", 0)) + 1
                    logger.info(f"Login fallido: {u}")

                    if st.session_state["attempts"] >= policy.max_attempts:
                        st.session_state["lock_until"] = now_ts() + policy.lock_seconds
                        st.session_state["attempts"] = 0
                        send_alert(f"Bloqueo temporal por intentos fallidos. Usuario={u}", level="warning")
                        st.error("Demasiados intentos. Bloqueado temporalmente.")
                    else:
                        st.error("Credenciales inválidas.")
    else:
        st.success(f"Sesión: {st.session_state.get('usuario')} ({st.session_state.get('role')})")
        # refresca actividad en cada render
        st.session_state["last_activity"] = now_ts()

        if st.button("Cerrar sesión"):
            user = st.session_state.get("usuario")
            st.session_state.clear()
            logger.info(f"Logout: {user}")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.write("")

    st.session_state["auto_alerts"] = st.checkbox(
        "Alertas automáticas", value=st.session_state.get("auto_alerts", False)
    )

    # --- contador de sesión restante por inactividad ---
    session_left = None
    if st.session_state.get("usuario") is not None:
        last = st.session_state.get("last_activity", 0.0) or 0.0
        session_left = int(policy.session_idle_seconds - (now_ts() - last))

    attempts_left = max(0, policy.max_attempts - int(st.session_state.get("attempts", 0)))
    locked = bool(st.session_state.get("lock_until", 0.0) and now_ts() < st.session_state["lock_until"])

    # Llamada compatible (si tu ui.py aún tiene la versión de 3 args)
    try:
        security_status_panel(attempts_left, st.session_state["auto_alerts"], locked, session_left)
    except TypeError:
        security_status_panel(attempts_left, st.session_state["auto_alerts"], locked)

    st.write("")

    # -----------------------
    # Recuperación local (reset de usuarios)
    # -----------------------
    with st.expander("🧯 Recuperación local (reset de usuarios)", expanded=False):
        st.caption("Úsalo solo si NO puedes iniciar sesión. Restablece admin/auditor/usuario por defecto.")
        code = st.text_input("Escribe: RESET-USME-2026 para confirmar", type="password", key="reset_code")
        if st.button("Restablecer usuarios (local)", key="btn_reset_users"):
            if (code or "").strip() == "RESET-USME-2026":
                reset_users()
                st.success("Usuarios restablecidos. Ahora puedes entrar con admin/admin123.")
                st.rerun()
            else:
                st.error("Código incorrecto. No se realizó el reset.")


# -----------------------
# Tabs (siempre al menos una)
# -----------------------
tab_map = {}

if st.session_state.get("usuario") is None:
    t_inicio = st.tabs(["Inicio"])[0]
    tab_map["Inicio"] = t_inicio
else:
    tabs = []
    role = st.session_state.get("role")

    # Admin y Usuario procesan
    if role in ("admin", "usuario"):
        tabs.append("Procesar")

    # Todos autenticados ven auditoría
    tabs.append("Auditoría")

    # Solo admin gestiona usuarios
    if role == "admin":
        tabs.append("Admin")

    created = st.tabs(tabs)
    for name, tab in zip(tabs, created):
        tab_map[name] = tab


# -----------------------
# TAB: Inicio (sin sesión)
# -----------------------
if "Inicio" in tab_map:
    with tab_map["Inicio"]:
        st.markdown("## 👋 Bienvenido")
        st.write(
            "Inicia sesión desde el panel izquierdo.\n\n"
            "**Roles:**\n"
            "- **Admin**: Procesar + Auditoría + Administración\n"
            "- **Usuario**: Procesar + Auditoría\n"
            "- **Auditor**: Solo Auditoría\n"
        )


# -----------------------
# TAB: Procesar
# -----------------------
if "Procesar" in tab_map:
    with tab_map["Procesar"]:
        st.markdown("## 📊 Generador de Plantilla Cargue Masivo CRP")
        st.caption("Sube PDFs y el Excel de equivalencias CDP. La app genera plantilla + reporte de inconsistencias.")

        if st.session_state.get("usuario") is None:
            st.warning("Debes iniciar sesión para usar el generador.")
            st.stop()

        # Seguridad extra: auditor no procesa (aunque idealmente el auditor no verá este tab)
        if st.session_state.get("role") == "auditor":
            st.warning("🔎 El rol AUDITOR es solo de lectura. No tiene permiso para generar plantillas.")
            st.stop()

        st.markdown('<div class="card">', unsafe_allow_html=True)
        pdfs = st.file_uploader("📄 PDFs de contratos", type=["pdf"], accept_multiple_files=True)
        excel_equiv = st.file_uploader("📎 Excel equivalencias CDP", type=["xlsx"])
        st.markdown("</div>", unsafe_allow_html=True)
        st.write("")

        if st.button("🚀 Generar plantilla", key="btn_generate"):
            if not pdfs or not excel_equiv:
                st.error("Debes subir PDFs y el Excel de equivalencias.")
                st.stop()

            try:
                df_cdp = pd.read_excel(excel_equiv, engine="openpyxl")

                col_cdp = next((c for c in df_cdp.columns if "cdp" in str(c).lower()), None)
                col_interno = next((c for c in df_cdp.columns if "interno" in str(c).lower()), None)
                col_objeto = next((c for c in df_cdp.columns if "objeto" in str(c).lower()), None)

                if not all([col_cdp, col_interno, col_objeto]):
                    st.error("El Excel debe tener columnas CDP, Interno y Objeto.")
                    st.stop()

                mapa_cdp = {
                    str(r[col_cdp]).strip(): {
                        "NoInterno": str(r[col_interno]).strip(),
                        "Objeto": str(r[col_objeto]).strip(),
                    }
                    for _, r in df_cdp.iterrows()
                }

                fixed = fixed_fields()
                all_records = []
                all_issues = []

                progress = st.progress(0.0)
                total = len(pdfs)

                for i, f in enumerate(pdfs, start=1):
                    try:
                        rows = extract_rows_from_pdf(f.read())
                        records, issues = build_records(rows, mapa_cdp, fixed, fuente_pdf=f.name)
                        all_records.extend(records)
                        all_issues.extend(issues)
                        logger.info(f"Procesado PDF: {f.name} records={len(records)} issues={len(issues)}")
                    except Exception as e:
                        st.warning(f"⚠️ Error procesando {f.name}: {e}")
                        logger.error(f"Error procesando {f.name}: {e}")
                        if st.session_state.get("auto_alerts"):
                            send_alert(f"Error procesando {f.name}: {e}", level="error")
                    progress.progress(i / total)

                if not all_records:
                    st.warning("No se encontraron registros válidos.")
                    st.stop()

                df = pd.DataFrame(all_records)
                df["CRP"] = range(1, len(df) + 1)
                df["Num. Ext. Entidad"] = range(1, len(df) + 1)

                columnas_finales = [
                    "CRP", "Posición", "Fecha Documento", "Fecha Contabilización",
                    "Sociedad", "Clase Documento", "Moneda", "Importe", "CDP",
                    "Posición del CDP", "Objeto", "Tipo de compromiso",
                    "No. Compromiso", "Fecha Inicial", "Fecha Final",
                    "Tipo de Pago", "Modo Selección",
                    "Tipo Documento Beneficiario", "Identificación Beneficiario",
                    "ID Solicitante", "ID Responsable",
                    "Num. Ext. Entidad", "CDP Original", "Fuente PDF",
                ]

                df_final = df[columnas_finales]
                df_issues = pd.DataFrame(all_issues)

                st.success("✅ Plantilla generada")
                st.dataframe(df_final, width="stretch")

                if not df_issues.empty:
                    st.warning(f"Se detectaron inconsistencias ({len(df_issues)})")
                    st.dataframe(df_issues, width="stretch")
                else:
                    st.info("🎉 Sin inconsistencias")

                output = build_output_excel(df_final, df_issues)
                filename = f"Plantilla_CRP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

                # Descarga (admin/usuario)
                if st.session_state.get("role") in ("admin", "usuario"):
                    st.download_button(
                        "📥 Descargar Excel (Plantilla + Inconsistencias)",
                        output,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    st.info("Descarga no disponible para tu rol.")

                # Guardar copia local
                salida = os.path.join(SALIDAS_DIR, filename)
                with open(salida, "wb") as out:
                    out.write(output.getvalue())
                logger.info(f"Plantilla guardada: {salida}")

            except Exception as e:
                st.error(f"❌ Error general: {e}")
                logger.error(str(e))
                if st.session_state.get("auto_alerts"):
                    send_alert(f"Error general: {e}", level="error")


# -----------------------
# TAB: Auditoría
# -----------------------
if "Auditoría" in tab_map:
    with tab_map["Auditoría"]:
        st.markdown("## 📁 Auditoría y seguridad")
        st.caption("Revisa accesos, bloqueos, errores y alertas registradas.")

        st.markdown('<div class="card">', unsafe_allow_html=True)

        accesos_txt = ""
        alerts_txt = ""

        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                accesos_txt = f.read()
            st.text_area("accesos.log", accesos_txt, height=280)
        else:
            st.info("No hay accesos.log aún.")

        st.write("")

        if os.path.exists(ALERTS_LOG):
            with open(ALERTS_LOG, "r", encoding="utf-8", errors="replace") as f:
                alerts_txt = f.read()
            st.text_area("alerts.log", alerts_txt, height=200)
        else:
            st.info("No hay alerts.log aún.")

        st.markdown("</div>", unsafe_allow_html=True)
        st.write("")

        # Descargar auditoría a Excel (solo admin y auditor)
        if st.session_state.get("role") in ("admin", "auditor"):
            audit_xlsx = build_audit_excel(accesos_txt, alerts_txt)
            st.download_button(
                "📥 Descargar Auditoría (Excel)",
                audit_xlsx,
                file_name=f"Auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("Tu rol no puede descargar auditoría.")


# -----------------------
# TAB: Admin (solo admin)
# -----------------------
if "Admin" in tab_map:
    with tab_map["Admin"]:
        st.markdown("## 🛡️ Admin — Gestión de usuarios")
        st.caption("Solo administradores: crea/actualiza usuarios con contraseñas hasheadas.")

        if st.session_state.get("role") != "admin":
            st.error("Acceso denegado.")
            st.stop()

        st.markdown('<div class="card">', unsafe_allow_html=True)

        new_user = st.text_input("Nuevo usuario", key="admin_new_user")
        new_pass = st.text_input("Nueva clave", type="password", key="admin_new_pass")
        new_role = st.selectbox("Rol", ["usuario", "auditor", "admin"], index=0, key="admin_new_role")

        if st.button("Crear / Actualizar usuario", key="btn_admin_upsert"):
            if not new_user or not new_pass:
                st.error("Usuario y clave son obligatorios.")
            else:
                upsert_user(new_user.strip(), new_pass, new_role)
                logger.info(f"Admin actualizó usuario={new_user} role={new_role}")
                st.success("✅ Usuario actualizado (contraseña hasheada).")

        st.markdown("</div>", unsafe_allow_html=True)