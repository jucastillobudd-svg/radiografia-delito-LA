# Radiografía del delito en Los Ángeles (2020–2023)

**Certamen 2 — Taller de Visualización de la Información** · Universidad del Desarrollo (UDD)

**Integrantes:** Juan Pablo Castillo · Martín Cáceres · Emilio Pacheco

Análisis exploratorio de los delitos denunciados al Departamento de Policía de Los Ángeles (LAPD) entre 2020 y 2023. El análisis busca responder **dónde, cuándo, a quién y cómo** ocurre el delito, como base para priorizar zonas y horarios de patrullaje y prevención.

---

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `Certamen2_Entrega_Final_Radiografia_delito_LA.ipynb` | Notebook de Google Colab con el análisis completo, organizado en 7 bloques |
| `README.md` | Este archivo |

**Notebook en Colab (solo lectura):** https://colab.research.google.com/drive/1aj-YRkaptJvExkcJxiLbIUE466P_oX1g

---

## Dataset

| | |
|---|---|
| **Nombre** | Crimes in Los Angeles 2020–2023 |
| **Fuente original** | Los Angeles Police Department (LAPD) |
| **Publicado en** | Kaggle (asaniczka): https://www.kaggle.com/datasets/asaniczka/crimes-in-los-angeles-2020-2023 |
| **Archivo** | `Crime_Data_from_2020_to_Present.csv` (CSV, 249 MB) |
| **Tamaño** | 852.950 filas × 27 columnas |
| **Período** | 01-01-2020 al 04-12-2023 |
| **Licencia** | CC0 (dominio público) |
| **Fecha de acceso** | 06-10-2026 |

> El CSV **no está incluido en este repositorio**: pesa 249 MB y GitHub no admite archivos de más de 100 MB. Hay que descargarlo desde Kaggle (link de arriba).

---

## Cómo ejecutar el notebook

1. Descargar `Crime_Data_from_2020_to_Present.csv` desde Kaggle.
2. Abrir `Certamen2_Entrega_Final_Radiografia_delito_LA.ipynb` en Google Colab (o usar el link de arriba).
3. En el panel lateral de **Archivos** de Colab, subir el CSV a `/content/` y esperar a que termine de cargar.
4. Ejecutar todo: **Entorno de ejecución → Ejecutar todas**.

No se necesita instalar nada: las librerías usadas (`numpy`, `pandas`, `matplotlib` y `seaborn`) vienen preinstaladas en Colab. La ruta del archivo está definida en la celda de carga (`ruta = "/content/Crime_Data_from_2020_to_Present.csv"`).

---

## Estructura del análisis

| Bloque | Pregunta | Contenido principal |
|---|---|---|
| **1. Perfil general** | ¿Qué datos tengo? | Carga, `info()`, diccionario de variables y corrección de tipos |
| **2. Calidad de los datos** | ¿Qué tan completos y confiables son? | Nulos por variable, duplicados, inconsistencias, decisiones de limpieza y comparación antes/después |
| **3. Exploración univariada** | ¿Cómo se comporta cada variable? | Edad y retraso de la denuncia (`histplot`, `boxplot`, `kdeplot`); top 10 de delito, lugar y arma (`countplot`) |
| **4. Mapas** | ¿Dónde ocurre el delito? | Mapa de puntos por gravedad (muestra de 100.000), mapa de densidad (`kdeplot`) y mapa de dos delitos de vehículo en 2023 |
| **5. Valores atípicos** | ¿Qué valores se salen de lo esperado? | Regla IQR, tabla de cantidad y %, boxplots antes/después y decisión justificada |
| **6. Exploración temporal** | ¿Cómo cambian los datos en el tiempo? | Delitos por mes y año (`lineplot`), por día de la semana y por hora (`barplot`) |
| **7. Relaciones entre variables** | ¿Qué variables se mueven juntas? | Correlaciones de Pearson y Spearman (`heatmap`), `pairplot`, box/violín por tipo de delito y tablas cruzadas |

Todas las visualizaciones están hechas con **Seaborn**.

---

## Decisiones principales

- **Nulos con significado:** el arma vacía se reemplaza por "Sin arma"; el sexo, el origen y el lugar vacíos se reemplazan por "Sin dato". No se elimina ninguna columna.
- **Edad 0 o negativa:** se excluye solo del análisis de edad (`df_edad`), porque corresponde a delitos sin una persona como víctima.
- **Coordenadas (0,0):** 2.263 registros se excluyen solo de los mapas (`df_mapa`), porque el LAPD las define como ubicación faltante.
- **Muestra para los mapas:** 100.000 puntos con `random_state=42`. La muestra reproduce las proporciones del total: la diferencia máxima es de 0,14 puntos porcentuales por área y de 0,07 por gravedad.
- **Valores atípicos:** se mantienen todos, porque son casos reales del dominio.
- **Diciembre de 2023:** se excluye del análisis temporal, porque los datos terminan el 4 de diciembre.
- **Las 12:00:** se señalan como hora por defecto de registro, no como hora real de más delitos.
