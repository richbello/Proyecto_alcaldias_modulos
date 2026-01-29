import streamlit as st
import os
import pdfplumber
import pandas as pd
import re
from datetime import datetime
import logging
from time import sleep
import shutil
import io

# -----------------------
# Configuración general
# -----------------------
st.set_page_config(page_title="Alcaldía Local de Usme", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SALIDAS_DIR = os.path.join(BASE_DIR, "salidas")
LOG_DIR = os.path.join(BASE_DIR, "logs")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(SALIDAS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "accesos.log")
ALERTS_LOG = os.path.join(LOG_DIR, "alerts.log")

# Configurar logger con encoding utf-8 para evitar problemas futuros
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == LOG_PATH for h in logger.handlers):
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# -----------------------
# Helper: rerun seguro (se mantiene pero no obligatorio usarlo)
# -----------------------
def safe_rerun():
    """
    Intenta st.experimental_rerun(); si no está disponible, fuerza una recarga
    asignando st.query_params (API pública) y deteniendo la ejecución con st.stop().
    """
    try:
        st.experimental_rerun()
        return
    except Exception:
        pass
    try:
        current = dict(st.query_params) if getattr(st, "query_params", None) is not None else {}
    except Exception:
        current = {}
    current["_rerun"] = datetime.utcnow().isoformat()
    try:
        st.query_params = current
        st.stop()
    except Exception:
        return

# -----------------------
# Estado inicial (todas las claves usadas en session_state)
# -----------------------
if "usuario" not in st.session_state:
    st.session_state["usuario"] = None
if "df_final" not in st.session_state:
    st.session_state["df_final"] = None
if "uploaded_flag" not in st.session_state:
    st.session_state["uploaded_flag"] = False
if "processing" not in st.session_state:
    st.session_state["processing"] = False
if "auto_start" not in st.session_state:
    st.session_state["auto_start"] = False
# Inicialización explícita solicitada:
if "auto_alerts" not in st.session_state:
    st.session_state["auto_alerts"] = False
if "roles_uploaded" not in st.session_state:
    st.session_state["roles_uploaded"] = False
if "ROLES" not in st.session_state:
    st.session_state["ROLES"] = {"admin": "admin123", "auditor": "audit456", "usuario": "user789"}
# Flag para mostrar la parte funcional tras login
if "show_main" not in st.session_state:
    st.session_state["show_main"] = False

# -----------------------
# Utilidades
# -----------------------
def limpiar_numero(s):
    if not s or s in ["-", ""]:
        return 0
    s = str(s).replace(".", "").replace(",", "").replace("$", "").strip()
    return int(re.sub(r"\D", "", s)) if any(ch.isdigit() for ch in s) else 0

def normalizar_texto(t):
    return re.sub(r"\s+", " ", str(t).strip()) if t else ""

def tipo_compromiso(obj):
    obj = obj.lower() if obj else ""
    if "servicios profesionales" in obj:
        return 145
    if "servicios de apoyo" in obj:
        return 148
    return 0

@st.cache_data(ttl=300)
def leer_excel_bytes(file_bytes):
    # Si file_bytes es un UploadedFile, pandas lo maneja; si no, será bytes
    try:
        return pd.read_excel(file_bytes, engine="openpyxl")
    except Exception:
        # fallback: si es UploadedFile, leer bytes y usar BytesIO
        try:
            file_bytes.seek(0)
            data = file_bytes.read()
            return pd.read_excel(io.BytesIO(data), engine="openpyxl")
        except Exception:
            raise

def load_credentials_from_file(uploaded_file):
    try:
        fname = uploaded_file.name.lower()
        if fname.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception as e:
        st.error(f"Error leyendo archivo de credenciales: {e}")
        return {}
    cols = {c.lower(): c for c in df.columns}
    user_col = None
    pass_col = None
    for k in cols.keys():
        if "user" in k or "usuario" in k or "login" in k:
            user_col = cols[k]
        if "pass" in k or "clave" in k or "password" in k:
            pass_col = cols[k]
    if not user_col or not pass_col:
        st.error("El archivo debe contener columnas con nombres tipo 'usuario' y 'clave' (o 'username' y 'password').")
        return {}
    roles = {}
    for _, r in df.iterrows():
        u = str(r[user_col]).strip()
        p = str(r[pass_col]).strip()
        if u:
            roles[u] = p
    return roles

def version_report():
    if not os.path.exists(LOG_PATH):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(LOG_DIR, f"accesos_report_{ts}.log")
    try:
        shutil.copy2(LOG_PATH, dst)
        return dst
    except Exception:
        return None

def send_alert(message, level="info"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - ALERT - {level.upper()} - {message}\n"
    try:
        with open(ALERTS_LOG, "a", encoding="utf-8") as fa:
            fa.write(line)
    except Exception:
        pass
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fl:
            fl.write(line)
    except Exception:
        pass
    logging.info(f"ALERTA: {message}")
    return True

# -----------------------
# Estilos principales (sin cambios funcionales)
# -----------------------
st.markdown(
    """
    <style>
    :root{
      --bg: #f6f7f9;
      --card: #ffffff;
      --muted: #6b7280;
      --text: #0f1724;
      --accent-yellow: #FFD100;
      --cta-red: #CE1126;
      --blue-accent: #0b57a4;
      --glass: rgba(15,23,36,0.04);
    }
    .stApp, .block-container, .main, .reportview-container .main .block-container {
      padding-top: 0 !important;
      margin-top: 0 !important;
      background: var(--bg) !important;
    }
    .app-wrap { padding: 8px 14px !important; margin-top: 0 !important; }
    .card { background: var(--card); border-radius: 12px; padding: 14px; box-shadow: 0 6px 18px rgba(12,18,28,0.06); }
    .stButton>button {
      border-radius: 8px; padding: 8px 14px; font-weight: 600; border: none; cursor: pointer;
      color: #fff !important; background: var(--cta-red) !important; box-shadow: 0 6px 14px rgba(206,17,38,0.12);
    }
    .stButton>button.btn-alt, .btn-alt { background: linear-gradient(90deg,var(--accent-yellow), #ffdf66) !important; color: #081226 !important; box-shadow: 0 6px 12px rgba(0,0,0,0.06) !important; }
    .tag { display:inline-block; padding:6px 10px; background: var(--blue-accent); color:#ffffff !important; border-radius:8px; font-size:12px; font-weight:700; margin-bottom:6px; }
    .stTextInput>div>div>input, .stTextInput>div>div>textarea, input[type="text"], input[type="password"] { background: #ffffff !important; color: var(--text) !important; border-radius: 6px !important; padding: 10px !important; border: 1px solid #e6e9ee !important; }
    .stFileUploader, .css-1d391kg, .css-1y4p8pa { background: linear-gradient(180deg,#ffffff,#fbfdff) !important; color: var(--text) !important; border-radius: 8px !important; padding: 10px !important; border: 1px solid #e6e9ee !important; }
    .stFileUploader .stButton>button, .stFileUploader [role="button"] { background: var(--blue-accent) !important; color: #ffffff !important; border-radius: 6px !important; padding: 6px 10px !important; box-shadow: none !important; border: 1px solid rgba(0,0,0,0.06) !important; }
    .notice-warning { background: #FFF8E1; color: #1f2933; padding: 12px 16px; border-left: 6px solid var(--accent-yellow); border-radius: 8px; margin-bottom: 8px; }
    .notice-info { background: #EAF6FF; color: #08345a; padding: 12px 16px; border-left: 6px solid var(--blue-accent); border-radius: 8px; margin-bottom: 8px; }
    label, .stText, .stMarkdown { color: var(--text) !important; }
    .flag-top { display:none !important; }
    @media (max-width:900px) { .app-wrap { padding: 6px 8px !important; } .stFileUploader, .css-1d391kg, .css-1y4p8pa { padding: 8px !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------
# Layout principal
# -----------------------
st.markdown('<div class="app-wrap">', unsafe_allow_html=True)

col_left, col_main = st.columns([1, 3], gap="large")

# -----------------------
# PANEL IZQUIERDO (LOGIN + REPORTES)
# -----------------------
with col_left:
    st.markdown('<div class="card" style="position:relative;">', unsafe_allow_html=True)
    st.markdown('<div style="font-weight:700; color:var(--accent-yellow); margin-bottom:8px;">🔒 Inicio de sesión</div>', unsafe_allow_html=True)

    creds_file = st.file_uploader("Subir credenciales (Excel/CSV) — opcional", type=["xlsx", "xls", "csv"], key="creds_uploader_left")
    if creds_file is not None:
        roles_loaded = load_credentials_from_file(creds_file)
        if roles_loaded:
            st.session_state["ROLES"] = roles_loaded
            st.session_state["roles_uploaded"] = True
            st.success("Credenciales cargadas correctamente (se usarán para el inicio de sesión).")

    usuario_input = st.text_input("Usuario", key="u_input_left")
    clave_input = st.text_input("Clave", type="password", key="p_input_left")

    if st.button("Ingresar", key="btn_login_left"):
        ROLES = st.session_state.get("ROLES", {})
        if usuario_input in ROLES and ROLES[usuario_input] == clave_input:
            st.session_state["usuario"] = usuario_input
            st.session_state["show_main"] = True  # mostrar la parte funcional inmediatamente
            logging.info(f"Login exitoso: {usuario_input}")
        else:
            st.error("Credenciales inválidas")

    if st.session_state["usuario"] is not None:
        st.markdown(f"**Sesión activa**  \n{st.session_state['usuario']}")
        if st.button("Cerrar sesión", key="btn_logout_left"):
            st.session_state.clear()
            # restaurar defaults
            st.session_state["ROLES"] = {"admin": "admin123", "auditor": "audit456", "usuario": "user789"}
            st.session_state["show_main"] = False

    st.markdown("---")
    st.markdown("### 📁 Reportes & Alertas")
    if st.button("Ver Reporte de Seguridad (accesos.log)"):
        if os.path.exists(LOG_PATH):
            # Lectura robusta del archivo de logs con fallback de codificaciones
            text = ""
            try:
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                try:
                    with open(LOG_PATH, "r", encoding="latin-1") as f:
                        text = f.read()
                except Exception:
                    with open(LOG_PATH, "rb") as f:
                        text = f.read().decode("utf-8", errors="replace")
            st.text_area("Reporte de Seguridad (accesos.log)", text, height=300)
        else:
            st.info("No hay registros de seguridad.")

    if st.button("Versionar reporte (crear copia)"):
        dst = version_report()
        if dst:
            st.success(f"Reporte versionado: {os.path.basename(dst)}")
        else:
            st.error("No se pudo versionar el reporte (¿existe accesos.log?).")

    if st.checkbox("Habilitar alertas automáticas en errores", value=st.session_state.get("auto_alerts", False), key="auto_alerts_checkbox"):
        st.session_state["auto_alerts"] = True
    else:
        st.session_state["auto_alerts"] = False

    if st.button("Enviar alerta manual (simulada)"):
        send_alert("Alerta manual enviada desde interfaz", level="warning")
        st.success("Alerta registrada y (simulada) enviada.")

    st.markdown('</div>', unsafe_allow_html=True)

# -----------------------
# PANEL PRINCIPAL (HERO + FUNCIONALIDAD)
# -----------------------
with col_main:
    st.markdown('<div class="card" style="position:relative;">', unsafe_allow_html=True)

    # Header: usar imagen del escudo si está disponible en assets (escudo.png o escudo.jpg)
    logo_png = os.path.join(ASSETS_DIR, "escudo.png")
    logo_jpg = os.path.join(ASSETS_DIR, "escudo.jpg")
    header_cols = st.columns([1, 5], gap="small")
    with header_cols[0]:
        if os.path.exists(logo_png):
            st.image(logo_png, width=140)
        elif os.path.exists(logo_jpg):
            st.image(logo_jpg, width=140)
        else:
            # fallback SVG dentro de un cuadro blanco
            st.markdown(
                """
                <div style="width:140px;height:140px;border-radius:12px;background:linear-gradient(180deg,#ffd100,#ffdf66);display:flex;align-items:center;justify-content:center;box-shadow:0 6px 18px rgba(0,0,0,0.08);">
                  <div style="width:84px;height:84px;background:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;">
                    <svg width="48" height="48" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="emblema">
                      <rect width="120" height="120" rx="12" fill="#ffd100"/>
                      <path d="M36 44c8-12 20-12 28 0 8-12 20-12 28 0v8c-16-6-28 8-56 0z" fill="#000"/>
                      <circle cx="36" cy="86" r="6" fill="#d21b2b"/>
                      <circle cx="84" cy="86" r="6" fill="#d21b2b"/>
                    </svg>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with header_cols[1]:
        st.markdown(
            """
            <div style="margin-left:4px;">
              <div style="font-size:28px;font-weight:800;color:#081226;">Alcaldía Local de Usme</div>
              <div style="color:#6b7280;margin-top:6px;">Gestión segura de Cargue Masivo CRP — Interfaz con identidad local</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr/>", unsafe_allow_html=True)

    # Mostrar avisos si no autenticado
    if not st.session_state.get("show_main", False) or st.session_state.get("usuario") is None:
        st.markdown('<div class="notice-warning">Debes autenticarse en el panel izquierdo para acceder a las funciones de carga y generación de plantillas.</div>', unsafe_allow_html=True)
        st.markdown('<div class="notice-info">Después de iniciar sesión podrás subir archivos y generar la plantilla CRP.</div>', unsafe_allow_html=True)
    else:
        st.markdown("### 📊 Generador de Plantilla Cargue Masivo CRP")
        st.markdown("**Alcaldía Local de Usme**")
        st.markdown("")

        def on_upload():
            st.session_state["uploaded_flag"] = True
            st.session_state["auto_start"] = True

        st.markdown("**Sube los PDFs de contratos**  \nDrag and drop o Browse. Límite 200MB por archivo.")
        pdfs = st.file_uploader("PDFS contratos", type=["pdf"], accept_multiple_files=True, key="pdfs_main", on_change=on_upload)

        st.markdown("**Sube el Excel de equivalencias CDP**  \nDrag and drop o Browse. Límite 200MB.")
        excel_equiv = st.file_uploader("Excel equivalencias CDP", type=["xlsx"], key="excel_main", on_change=on_upload)

        st.markdown("---")

        if st.session_state["uploaded_flag"] and not st.session_state["processing"]:
            st.markdown('<div class="notice-info">Se detectaron archivos nuevos. Pulsa Generar Plantilla o espera 2 segundos para inicio automático.</div>', unsafe_allow_html=True)
            sleep(2)

        start_now = st.button("Generar Plantilla", key="btn_generate") or st.session_state.get("auto_start", False)
        if start_now:
            st.session_state["auto_start"] = False
            if not pdfs or not excel_equiv:
                st.error("❌ Debes subir los PDFs y el Excel de equivalencias.")
            else:
                st.session_state["processing"] = True
                with st.spinner("⏳ Procesando archivos..."):
                    try:
                        # Intento principal: leer con la función cacheada (si es compatible)
                        try:
                            df_cdp = leer_excel_bytes(excel_equiv)
                        except Exception:
                            try:
                                excel_equiv.seek(0)
                            except Exception:
                                pass
                            df_cdp = pd.read_excel(io.BytesIO(excel_equiv.read()), engine="openpyxl")
                    except Exception as e:
                        st.error(f"Error leyendo Excel: {e}")
                        logging.error(f"Error leyendo Excel equivalencias: {e}")
                        if st.session_state.get("auto_alerts"):
                            send_alert(f"Error leyendo Excel equivalencias: {e}", level="error")
                        st.session_state["processing"] = False
                        raise

                    col_cdp = next((col for col in df_cdp.columns if "cdp" in str(col).lower()), None)
                    col_interno = next((col for col in df_cdp.columns if "interno" in str(col).lower()), None)
                    col_objeto = next((col for col in df_cdp.columns if "objeto" in str(col).lower()), None)
                    if not col_cdp or not col_interno or not col_objeto:
                        st.error("❌ El Excel no tiene las columnas esperadas (CDP, Interno, Objeto).")
                        st.session_state["processing"] = False
                    else:
                        mapa_cdp = {}
                        for _, fila in df_cdp.iterrows():
                            clave = str(fila[col_cdp]).strip()
                            mapa_cdp[clave] = {"NoInterno": str(fila[col_interno]).strip(), "Objeto": str(fila[col_objeto]).strip()}

                        fecha_actual = datetime.today().strftime("%d.%m.%Y")
                        fijos = {"Posición": "1", "Sociedad": "1001", "Clase Documento": "RP", "Moneda": "COP",
                                 "Fecha Documento": fecha_actual, "Fecha Contabilización": fecha_actual,
                                 "Fecha Inicial": fecha_actual, "Fecha Final": "31.12.2026",
                                 "Tipo de Pago": "02", "Modo Selección": "10", "Tipo Documento Beneficiario": "CC",
                                 "ID Solicitante": "1000131265", "ID Responsable": "1000835316"}

                        datos = []
                        total_pdfs = len(pdfs)
                        progress = st.progress(0)
                        for i, archivo in enumerate(pdfs, start=1):
                            try:
                                archivo_bytes = archivo.read()
                                with pdfplumber.open(io.BytesIO(archivo_bytes)) as pdf:
                                    for page in pdf.pages:
                                        for tabla in page.extract_tables() or []:
                                            for fila in tabla:
                                                if fila and len(fila) >= 10:
                                                    cdp_valor = str(fila[7]).strip()
                                                    datos_cdp = mapa_cdp.get(cdp_valor, {"NoInterno": "NO ENCONTRADO", "Objeto": "NO ENCONTRADO"})
                                                    datos.append({
                                                        "Importe": limpiar_numero(fila[9]),
                                                        "CDP": datos_cdp["NoInterno"],
                                                        "Posición del CDP": "1",
                                                        "Objeto": normalizar_texto(datos_cdp["Objeto"]),
                                                        "Tipo de compromiso": tipo_compromiso(datos_cdp["Objeto"]),
                                                        "No. Compromiso": normalizar_texto(fila[0]),
                                                        "Identificación Beneficiario": normalizar_texto(fila[4]),
                                                        **fijos
                                                    })
                                logging.info(f"Procesado PDF: {archivo.name}")
                            except Exception as e:
                                st.warning(f"⚠️ Error procesando {getattr(archivo, 'name', str(i))}: {e}")
                                logging.error(f"Error en PDF {getattr(archivo, 'name', str(i))}: {e}")
                                if st.session_state.get("auto_alerts"):
                                    send_alert(f"Error procesando {getattr(archivo, 'name', str(i))}: {e}", level="error")
                            progress.progress(int(i / total_pdfs * 100))

                        if datos:
                            df = pd.DataFrame(datos)
                            df["CRP"] = range(1, len(df) + 1)
                            df["Num. Ext. Entidad"] = range(1, len(df) + 1)
                            columnas_finales = ["CRP", "Posición", "Fecha Documento", "Fecha Contabilización", "Sociedad", "Clase Documento",
                                                "Moneda", "Importe", "CDP", "Posición del CDP", "Objeto", "Tipo de compromiso",
                                                "No. Compromiso", "Fecha Inicial", "Fecha Final", "Tipo de Pago", "Modo Selección",
                                                "Tipo Documento Beneficiario", "Identificación Beneficiario", "ID Solicitante", "ID Responsable",
                                                "Num. Ext. Entidad"]
                            df_final = df[columnas_finales]
                            st.session_state["df_final"] = df_final

                            # Mostrar resultado en pantalla
                            st.markdown("#### Resultado: vista previa de la plantilla generada")
                            st.dataframe(df_final, use_container_width=True)

                            # Guardar copia en disco para trazabilidad
                            salida = os.path.join(SALIDAS_DIR, f"Plantilla_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
                            df_final.to_excel(salida, index=False)

                            # Preparar descarga en memoria (BytesIO) y botón de descarga
                            towrite = io.BytesIO()
                            df_final.to_excel(towrite, index=False, engine="openpyxl")
                            towrite.seek(0)
                            st.download_button("📥 Descargar Excel", towrite, file_name=os.path.basename(salida), mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                            # Botón "Volver" para limpiar estado y regresar a la vista de carga
                            if st.button("🔙 Volver"):
                                st.session_state["df_final"] = None
                                st.session_state["uploaded_flag"] = False
                                st.session_state["processing"] = False
                                # limpiar uploaders en session_state si existen
                                for key in ("pdfs_main", "excel_main"):
                                    if key in st.session_state:
                                        try:
                                            st.session_state[key] = None
                                        except Exception:
                                            pass
                                logging.info("Usuario pulsó Volver - retorno al estado de carga")
                                try:
                                    safe_rerun()
                                except Exception:
                                    try:
                                        st.experimental_rerun()
                                    except Exception:
                                        pass

                            logging.info("Plantilla generada y guardada.")
                        else:
                            st.warning("⚠️ No se encontraron registros válidos en los PDFs.")
                        st.session_state["processing"] = False
                        st.session_state["uploaded_flag"] = False

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)