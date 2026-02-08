# modules/reports.py
import io
import re
import pandas as pd

def build_output_excel(df_plantilla: pd.DataFrame, df_issues: pd.DataFrame) -> io.BytesIO:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_plantilla.to_excel(writer, index=False, sheet_name="Plantilla_CRP")
        df_issues.to_excel(writer, index=False, sheet_name="Inconsistencias")
    output.seek(0)
    return output

def parse_log_text(text: str) -> pd.DataFrame:
    # Formato esperado: "YYYY-MM-DD HH:MM:SS,ms - mensaje"
    rows = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d{4}-\d{2}-\d{2}[^-]+)\s-\s(.+)$", line)
        if m:
            rows.append({"timestamp": m.group(1).strip(), "mensaje": m.group(2).strip()})
        else:
            rows.append({"timestamp": "", "mensaje": line})
    return pd.DataFrame(rows)

def build_audit_excel(accesos_text: str, alerts_text: str) -> io.BytesIO:
    df_acc = parse_log_text(accesos_text)
    df_alr = parse_log_text(alerts_text)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_acc.to_excel(writer, index=False, sheet_name="Accesos")
        df_alr.to_excel(writer, index=False, sheet_name="Alertas")
    output.seek(0)
    return output