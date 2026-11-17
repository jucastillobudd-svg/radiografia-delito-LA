# preparar_datos.py
# ============================================================
#  Genera data/delitos_LA_limpio.csv.gz a partir del CSV original
#  de Kaggle, aplicando la MISMA limpieza del Certamen 2.
#
#  Se ejecuta UNA vez en el computador (no en Streamlit Cloud):
#      python preparar_datos.py
#  El CSV original (249 MB) no se sube a GitHub: debe estar en la
#  carpeta de arriba o en esta misma carpeta.
#
#  Resultado: 851.405 delitos (ene-2020 a nov-2023), 13 columnas,
#  ~19 MB comprimido en .gz -> bajo el límite de 25 MB de la pauta,
#  así que el dashboard usa el dataset COMPLETO, sin muestra.
# ============================================================

from pathlib import Path

import pandas as pd

ORIGEN = "Crime_Data_from_2020_to_Present.csv"
DESTINO = Path("data/delitos_LA_limpio.csv.gz")

# Buscar el CSV original aquí o en la carpeta de arriba
ruta = Path(ORIGEN) if Path(ORIGEN).exists() else Path("..") / ORIGEN

# Solo las columnas que usa el dashboard
columnas = ["date_reported", "date_occurred", "area_name", "reporting_district", "part",
            "crime_description", "victim_age", "victim_sex", "premise_description",
            "weapon_description", "status_description", "latitude", "longitude"]
df = pd.read_csv(ruta, usecols=columnas)
print("Original:", df.shape)

# 1. Tipos: fechas (Bloque 1 del Certamen 2)
df["date_occurred"] = pd.to_datetime(df["date_occurred"])
df["date_reported"] = pd.to_datetime(df["date_reported"])

# 2. Corte: diciembre de 2023 solo tiene 4 días de datos (Bloque 6)
df = df[df["date_occurred"] < "2023-12-01"].copy()

# 3. Retraso de la denuncia en días (Bloque 3)
df["retraso_dias"] = (df["date_reported"] - df["date_occurred"].dt.normalize()).dt.days
df = df.drop(columns="date_reported")

# 4. Nulos (decisiones del Bloque 2)
df["weapon_description"] = df["weapon_description"].fillna("Sin arma")      # 65% vacío = no hubo arma
df["premise_description"] = df["premise_description"].fillna("Sin dato")
df["victim_sex"] = df["victim_sex"].replace({"H": "X", "-": "X"}).fillna("Sin dato")

# Edad 0 o negativa y coordenadas (0,0) NO se borran: se excluyen solo
# en el análisis que corresponde (edad y mapas), igual que en el Certamen 2.

DESTINO.parent.mkdir(exist_ok=True)
df.to_csv(DESTINO, index=False, compression="gzip")
print("Limpio:", df.shape, "->", DESTINO, f"({DESTINO.stat().st_size / 1e6:.1f} MB)")
