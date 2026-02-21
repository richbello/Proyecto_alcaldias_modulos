import pdfplumber
import re
import pandas as pd
import os

# Carpeta con los PDFs
folder = r"C:\RICHARD\FDL\Usme\2026\Pagos\Febrero\ENTREGA_3"
rows = []

def limpiar_numero(valor):
    """Convierte texto con puntos/comas a entero"""
    return int(valor.replace(".", "").replace(",", ""))

for file in os.listdir(folder):
    if file.endswith(".pdf"):
        pdf_path = os.path.join(folder, file)
        with pdfplumber.open(pdf_path) as pdf:
            texto = "\n".join([page.extract_text() for page in pdf.pages])

            datos = {
                "Contrato No": None,
                "Contratista": None,
                "NIT o CC": None,
                "Pago No": None,
                "Valor Bruto": None,
                "Base Reteica": None,
                "Reteica %": None,
                "Reteica Valor": None,
                "Total Descuentos": 0,
                "Neto a Pagar": None
            }

            # Contrato No
            contrato = re.search(r"CONTRATO No\.?\s*(CPS\s*\d+-\d+)", texto)
            if contrato:
                datos["Contrato No"] = contrato.group(1)

            # Contratista
            contratista = re.search(r"CONTRATISTA:\s*(.+)", texto)
            if contratista:
                datos["Contratista"] = contratista.group(1).strip()

            # NIT o CC
            nit = re.search(r"NIT\. o C\.C\.\s*([\d\.\-]+)", texto)
            if nit:
                datos["NIT o CC"] = nit.group(1)

            # Pago No
            pago = re.search(r"PAGO No\.\s*(\d+)", texto)
            if pago:
                datos["Pago No"] = int(pago.group(1))

            # Valor Bruto
            valor_bruto = re.search(r"VALOR BRUTO.*?\$ ?([\d\.,]+)", texto)
            if valor_bruto:
                bruto_raw = limpiar_numero(valor_bruto.group(1))
                datos["Valor Bruto"] = bruto_raw * 1_000_000 if bruto_raw < 1000 else bruto_raw

            # Reteica
            base_reteica = re.search(r"Reteica.*?\$ ?([\d\.,]+)", texto)
            if base_reteica:
                datos["Base Reteica"] = limpiar_numero(base_reteica.group(1))

            porcentaje_reteica = re.search(r"Reteica.*?(\d+[\.,]?\d*%)", texto)
            if porcentaje_reteica:
                datos["Reteica %"] = porcentaje_reteica.group(1)

            valor_reteica = re.search(r"Reteica.*?\$ ?([\d\.,]+)$", texto, re.MULTILINE)
            if valor_reteica:
                datos["Reteica Valor"] = limpiar_numero(valor_reteica.group(1))
                datos["Total Descuentos"] += datos["Reteica Valor"]

            # Otras retenciones (ejemplo: Retefuente, ReteIVA, etc.)
            otras_retenciones = re.findall(r"(Retefuente.*?|ReteIva).*?\$ ?([\d\.,]+)", texto)
            for _, valor in otras_retenciones:
                if valor.strip() not in ["-", ""]:
                    datos["Total Descuentos"] += limpiar_numero(valor)

            # Total Descuentos
            descuentos = re.search(r"TOTAL DESCUENTOS.*?\$ ?([\d\.,]+)", texto)
            if descuentos:
                datos["Total Descuentos"] = limpiar_numero(descuentos.group(1))

            # Neto a Pagar
            neto = re.search(r"NETO A PAGAR.*?\$ ?([\d\.,]+)", texto)
            if neto:
                datos["Neto a Pagar"] = limpiar_numero(neto.group(1))

            rows.append(datos)
            

# Exportar a Excel
df = pd.DataFrame(rows)
output_path = os.path.join(folder, "consolidado_pagos_usme_FEB2026.xlsx")
df.to_excel(output_path, index=False)

print("✅ Consolidado exportado correctamente a Excel:", output_path)


