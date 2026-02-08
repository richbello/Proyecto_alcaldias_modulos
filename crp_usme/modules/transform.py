# modules/transform.py
import re
from datetime import datetime

def limpiar_numero(s):
    if not s or s in ["-", ""]:
        return 0
    s = str(s).replace(".", "").replace(",", "").replace("$", "").strip()
    digits = re.sub(r"\D", "", s)
    return int(digits) if digits else 0

def normalizar_texto(t):
    return re.sub(r"\s+", " ", str(t).strip()) if t else ""

def tipo_compromiso(obj):
    obj = obj.lower() if obj else ""
    if "servicios profesionales" in obj:
        return 145
    if "servicios de apoyo" in obj:
        return 148
    return 0

def is_probable_cdp(value: str) -> bool:
    return bool(re.fullmatch(r"\d{3,}", (value or "").strip()))

def fixed_fields():
    fecha_actual = datetime.today().strftime("%d.%m.%Y")
    return {
        "Posición": "1",
        "Sociedad": "1001",
        "Clase Documento": "RP",
        "Moneda": "COP",
        "Fecha Documento": fecha_actual,
        "Fecha Contabilización": fecha_actual,
        "Fecha Inicial": fecha_actual,
        "Fecha Final": "31.12.2026",
        "Tipo de Pago": "02",
        "Modo Selección": "10",
        "Tipo Documento Beneficiario": "CC",
        "ID Solicitante": "1000131265",
        "ID Responsable": "1000835316",
    }

def build_records(rows, mapa_cdp: dict, fixed: dict, fuente_pdf: str):
    records = []
    issues = []

    for idx, fila in enumerate(rows, start=1):
        if not fila or len(fila) < 10:
            continue

        cdp_original = (fila[7] or "").strip() if len(fila) > 7 else ""
        importe = limpiar_numero(fila[9] if len(fila) > 9 else "")

        no_compromiso = normalizar_texto(fila[0]) if len(fila) > 0 else ""
        beneficiario = normalizar_texto(fila[4]) if len(fila) > 4 else ""

        row_issues = []
        if not cdp_original or not is_probable_cdp(cdp_original):
            row_issues.append("CDP_ORIGINAL_INVALIDO_O_VACIO")

        datos_cdp = mapa_cdp.get(cdp_original)
        if not datos_cdp:
            row_issues.append("CDP_NO_ENCONTRADO_EN_EQUIVALENCIAS")
            datos_cdp = {"NoInterno": "NO ENCONTRADO", "Objeto": "NO ENCONTRADO"}

        objeto = normalizar_texto(datos_cdp.get("Objeto", ""))
        if objeto == "NO ENCONTRADO":
            row_issues.append("OBJETO_NO_ENCONTRADO")

        if importe <= 0:
            row_issues.append("IMPORTE_EN_CERO_O_INVALIDO")

        if not beneficiario:
            row_issues.append("IDENTIFICACION_BENEFICIARIO_VACIA")

        record = {
            "Importe": importe,
            "CDP": datos_cdp.get("NoInterno", "NO ENCONTRADO"),
            "Posición del CDP": "1",
            "Objeto": objeto,
            "Tipo de compromiso": tipo_compromiso(objeto),
            "No. Compromiso": no_compromiso,
            "Identificación Beneficiario": beneficiario,
            "CDP Original": cdp_original,
            "Fuente PDF": fuente_pdf,
            **fixed,
        }

        if row_issues:
            issues.append({
                "Fuente PDF": fuente_pdf,
                "Fila PDF": idx,
                "CDP Original": cdp_original,
                "No. Compromiso": no_compromiso,
                "Importe": importe,
                "Problemas": ";".join(row_issues),
            })

        records.append(record)

    return records, issues