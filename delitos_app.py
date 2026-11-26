# delitos_app.py
# ============================================================
#  DASHBOARD — Radiografía del delito en Los Ángeles (2020–2023)
#  Taller de Visualización de la Información (UDD), Examen final
#  Juan Pablo Castillo, Martín Cáceres y Emilio Pacheco
#
#  Versión: 3.0.0 (Hito 2)
#
#  Ejecutar en local:  streamlit run delitos_app.py
#  Publicar:           repo en GitHub -> Streamlit Community Cloud
#
#  Pregunta del dashboard: ¿Dónde, cuándo y a quién debe priorizar
#  la prevención la Policía de Los Ángeles (LAPD)?
#
#  Idea clave de Streamlit: el script se ejecuta de arriba a abajo
#  cada vez que el usuario mueve un widget. Todo el dashboard es
#  código Python normal, leído en orden.
#
#  Estructura (misma plantilla que tips_app.py):
#   1. Configuración   2. Paleta y estilo   3. Carga de datos
#   4. Filtros globales (sidebar)   5. Máscara de filtros
#   6. Encabezado   7. KPIs   8–13. Pestañas con los gráficos
#   14. Tabla de datos
# ============================================================

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

VERSION = "3.0.0"
CARPETA = Path(__file__).parent / "data"   # funciona en local y en Streamlit Cloud

# ── 1. CONFIGURACIÓN DE LA PÁGINA ────────────────────────────
# Debe ser la primera instrucción de Streamlit del script.
st.set_page_config(
    page_title="Delitos en Los Ángeles",
    layout="wide",
)

# ── 2. PALETA DE COLORES Y ESTILO COMPARTIDO ─────────────────
# Mismos colores del Certamen 2 (navy, rojo, gris). Una categoría
# tiene siempre el mismo color en todos los gráficos.
AZUL, ROJO, GRIS, SALMON, DORADO = "#0b2545", "#8B1E1E", "#6c7480", "#e07a6f", "#c9a227"

COLOR_SEXO = {"Mujer": ROJO, "Hombre": AZUL, "Desconocido (X)": "#a9b0b9", "Sin dato": "#dde1e6"}
COLOR_GRAVEDAD = {"Grave": ROJO, "Menos grave": "#9aa3ad"}
COLOR_CATEGORIA = {
    "Violencia y amenazas": ROJO,
    "Vehículos": AZUL,
    "Robos y hurtos": "#3d7ea6",
    "Vandalismo": DORADO,
    "Fraude e identidad": "#7b5ea7",
    "Delitos sexuales": SALMON,
    "Otros": "#b8bec6",
}
COLOR_BURO = {"Central": ROJO, "Sur": AZUL, "Oeste": DORADO, "Valle": "#3d7ea6"}
COLOR_ESTADO = {"Con arresto": AZUL, "Cerrado sin arresto": "#3d7ea6", "En investigación": "#c5ccd4",
                "Desconocido": "#eef0f2"}
ESTADOS = list(COLOR_ESTADO)
LUGARES = ["Calle o espacio público", "Vivienda", "Estacionamiento", "Comercio y servicios",
           "Vehículo o transporte", "Otro lugar", "Sin dato"]
SECUENCIA = [AZUL, ROJO, DORADO, "#3d7ea6", SALMON, "#7b5ea7", GRIS]

DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
HORAS = [f"{h:02d}:00" for h in range(24)]

# Estilo de Plotly reutilizable: se "desempaqueta" con ** en cada
# fig.update_layout(**LAYOUT). separators=",." = formato chileno (1.234,5)
LAYOUT = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(family="Inter,Arial,sans-serif", size=12),
    separators=",.",
    margin=dict(t=50, b=40, l=50, r=20),
    hoverlabel=dict(bgcolor="white", font_size=12),
)

# Estilos de mapa base (sin token de Mapbox: los usa px.*_map)
ESTILOS_MAPA = {
    "Calles (claro)": "carto-positron",
    "Calles (color)": "carto-voyager",
    "OpenStreetMap": "open-street-map",
    "Oscuro": "carto-darkmatter",
}
CENTRO_LA = {"lat": 34.03, "lon": -118.40}

# 21 áreas LAPD agrupadas en 4 burós (oficinas de mando)
BURO = {
    "Central": "Central", "Hollenbeck": "Central", "Newton": "Central", "Northeast": "Central", "Rampart": "Central",
    "77th Street": "Sur", "Harbor": "Sur", "Southeast": "Sur", "Southwest": "Sur",
    "Hollywood": "Oeste", "Olympic": "Oeste", "Pacific": "Oeste", "West LA": "Oeste", "Wilshire": "Oeste",
    "Devonshire": "Valle", "Foothill": "Valle", "Mission": "Valle", "N Hollywood": "Valle",
    "Topanga": "Valle", "Van Nuys": "Valle", "West Valley": "Valle",
}

# Los 10 delitos más frecuentes en español (filtro "Tipo de delito")
TOP10 = {
    "VEHICLE - STOLEN": "Robo de vehículo",
    "BATTERY - SIMPLE ASSAULT": "Agresión simple",
    "THEFT OF IDENTITY": "Robo de identidad",
    "BURGLARY FROM VEHICLE": "Robo desde vehículo",
    "BURGLARY": "Robo a vivienda o local",
    "VANDALISM - FELONY ($400 & OVER, ALL CHURCH VANDALISMS)": "Vandalismo grave",
    "ASSAULT WITH DEADLY WEAPON, AGGRAVATED ASSAULT": "Agresión con arma",
    "THEFT PLAIN - PETTY ($950 & UNDER)": "Hurto simple",
    "INTIMATE PARTNER - SIMPLE ASSAULT": "Violencia de pareja",
    "THEFT FROM MOTOR VEHICLE - PETTY ($950 & UNDER)": "Hurto desde vehículo",
}
# 15 delitos más, para el detalle del sunburst (el resto = "Otros: <categoría>")
DETALLE = {**TOP10,
    "THEFT FROM MOTOR VEHICLE - GRAND ($950.01 AND OVER)": "Hurto desde vehículo (mayor)",
    "ROBBERY": "Asalto con violencia",
    "THEFT-GRAND ($950.01 & OVER)EXCPT,GUNS,FOWL,LIVESTK,PROD": "Hurto mayor",
    "VANDALISM - MISDEAMEANOR ($399 OR UNDER)": "Vandalismo menor",
    "SHOPLIFTING - PETTY THEFT ($950 & UNDER)": "Hurto en tienda",
    "CRIMINAL THREATS - NO WEAPON DISPLAYED": "Amenazas",
    "BRANDISH WEAPON": "Exhibir un arma",
    "TRESPASSING": "Ingreso ilegal a propiedad",
    "INTIMATE PARTNER - AGGRAVATED ASSAULT": "Violencia de pareja agravada",
    "VIOLATION OF RESTRAINING ORDER": "Violar orden de alejamiento",
    "BIKE - STOLEN": "Robo de bicicleta",
    "LETTERS, LEWD  -  TELEPHONE CALLS, LEWD": "Llamadas o cartas obscenas",
    "BUNCO, GRAND THEFT": "Estafa",
    "ATTEMPTED ROBBERY": "Intento de asalto",
    "RAPE, FORCIBLE": "Violación",
}

# Reglas para agrupar las 138 descripciones del LAPD en 7 categorías.
# Se revisan en orden y gana la primera que calza (por eso "THEFT OF
# IDENTITY" queda en Fraude y no en Robos).
REGLAS_CATEGORIA = [
    ("Fraude e identidad", r"IDENTITY|FORGERY|FRAUD|COUNTERFEIT|BUNCO|EMBEZZLEMENT|DOCUMENT WORTHLESS|DEFRAUD|DISHONEST EMPLOYEE|UNAUTHORIZED COMPUTER|BRIBERY|EXTORTION"),
    ("Delitos sexuales", r"RAPE|SEXUAL|SEX,|LEWD|ORAL COPULATION|SODOMY|INDECENT|PEEPING|PIMPING|PANDERING|COMMERCIAL SEX|INCEST|BEASTIALITY|PORNOGRAPHY|CRM AGNST CHLD"),
    ("Violencia y amenazas", r"ASSAULT|BATTERY|INTIMATE|ROBBERY|HOMICIDE|MANSLAUGHTER|KIDNAP|THREAT|BRANDISH|SHOTS|DISCHARGE FIREARMS|CHILD ABUSE|CHILD NEGLECT|CHILD ANNOY|CHILD STEALING|CHILD ABANDON|STALKING|FALSE IMPRISONMENT|LYNCHING|TRAFFICKING|THROWING OBJECT|WEAPONS POSSESSION|BOMB|RESISTING"),
    ("Vehículos", r"VEHICLE|BIKE|BOAT|DWOC"),
    ("Robos y hurtos", r"THEFT|BURGLARY|SHOPLIFTING|PICKPOCKET|PURSE|STOLEN|TILL TAP|DRUNK ROLL"),
    ("Vandalismo", r"VANDALISM|ARSON|ILLEGAL DUMPING|PROPERTY - DAMAGE"),
]
REGLAS_LUGAR = [
    ("Sin dato", r"^Sin dato$"),
    ("Estacionamiento", r"PARKING"),
    ("Vivienda", r"DWELLING|RESIDENCE|HOUSE|APARTMENT|CONDO|GARAGE|CARPORT|DRIVEWAY|YARD|PORCH|MOBILE HOME|PATIO|GROUP HOME|NURSING"),
    ("Vehículo o transporte", r"VEHICLE|BUS|TRAIN|MTA|METRO|TAXI|TRUCK|AIRCRAFT"),
    ("Calle o espacio público", r"STREET|SIDEWALK|ALLEY|HIGHWAY|FREEWAY|PARK|BEACH|BRIDGE|TUNNEL|PEDESTRIAN|VACANT LOT|RIVER"),
    ("Comercio y servicios", r"STORE|MARKET|RESTAURANT|BUSINESS|GAS STATION|MALL|HOTEL|MOTEL|BANK|OFFICE|BAR|CLUB|SHOP|DEPARTMENT|PHARMACY|CLINIC|HOSPITAL|THEATRE|GYM|LIQUOR|LAUNDROMAT|SALON|WAREHOUSE|BUILDING|COFFEE|FAST FOOD"),
]
REGLAS_ARMA = [
    ("Sin arma", r"^Sin arma$"),
    ("Fuerza física", r"STRONG-ARM"),
    ("Amenaza verbal", r"VERBAL THREAT"),
    ("Otra o desconocida", r"STUN GUN|BB GUN|TOY GUN|SIMULATED GUN|STARTER PISTOL|AIR PISTOL"),
    ("Arma de fuego", r"GUN|PISTOL|RIFLE|FIREARM|REVOLVER|SHOTGUN|DERRINGER|UZI|MAC-|SEMIAUTOMATIC|ASSAULT WEAPON"),
    ("Arma blanca", r"KNIFE|BLADE|DAGGER|SWORD|MACHETE|SCISSORS|AXE|ICE PICK|RAZOR|CLEAVER"),
]
ESTADO = {"Invest Cont": "En investigación", "Adult Arrest": "Con arresto", "Juv Arrest": "Con arresto",
          "Adult Other": "Cerrado sin arresto", "Juv Other": "Cerrado sin arresto", "UNK": "Desconocido"}


def clasificar(valor, reglas, otro="Otros"):
    """Devuelve la primera categoría cuya expresión calza con el texto."""
    for nombre, patron in reglas:
        if re.search(patron, valor):
            return nombre
    return otro


def mapear(serie, reglas, otro="Otros"):
    """Clasifica solo los valores únicos (138 delitos, no 850 mil filas) y luego usa .map()."""
    unicos = serie.dropna().unique()
    return serie.map({v: clasificar(v, reglas, otro) for v in unicos})


def fmt(n):
    """Número con punto de miles: 1234567 -> '1.234.567'."""
    return f"{int(round(n)):,}".replace(",", ".")


def pct(x, dec=1):
    """Porcentaje con coma decimal: 6.789 -> '6,8%'."""
    return f"{x:.{dec}f}%".replace(".", ",")


def num(x, dec=1):
    """Número con coma decimal: 1.5 -> '1,5'."""
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def lectura(texto):
    """Caja de interpretación escrita junto a cada gráfico."""
    st.info(f"**Lectura.** {texto}")


# ── 3. CARGAR Y PREPARAR LOS DATOS ───────────────────────────
# @st.cache_data: la función se ejecuta una sola vez y Streamlit
# guarda el resultado en memoria. Sin esta línea, cada clic en un
# filtro volvería a leer y limpiar los 851 mil delitos (~5 s cada vez).
@st.cache_data(show_spinner="Cargando 851 mil delitos (solo la primera vez)...")
def cargar_datos():
    # Dataset limpio del Certamen 2, completo (19 MB comprimido, ver preparar_datos.py).
    # Las columnas de texto se leen como 'category': el DataFrame ocupa ~55 MB en vez de ~410 MB.
    textos = ["area_name", "crime_description", "victim_sex", "premise_description",
              "weapon_description", "status_description"]
    df = pd.read_csv(CARPETA / "delitos_LA_limpio.csv.gz", parse_dates=["date_occurred"],
                     dtype={c: "category" for c in textos})

    # Variables de tiempo
    df["Fecha"] = df["date_occurred"].dt.normalize()
    df["Año"] = df["date_occurred"].dt.year
    df["Mes"] = df["date_occurred"].dt.to_period("M").dt.to_timestamp()
    df["Mes del año"] = df["date_occurred"].dt.month
    df["Hora"] = df["date_occurred"].dt.hour
    df["Día"] = df["date_occurred"].dt.day_name().map(dict(zip(DIAS_EN, DIAS_ES)))
    df["N° día"] = df["date_occurred"].dt.dayofweek + 1           # 1 = lunes ... 7 = domingo
    df["Tipo de día"] = df["N° día"].map(lambda d: "Fin de semana" if d >= 6 else "Lunes a viernes")

    # Dónde
    df["Área"] = df["area_name"]
    df["Buró"] = df["Área"].map(BURO)
    df["Distrito"] = df["reporting_district"]

    # Qué
    df["Delito"] = df["crime_description"].map(TOP10).fillna("Otros delitos")
    df["Categoría"] = mapear(df["crime_description"], REGLAS_CATEGORIA)
    df["Delito (detalle)"] = df["crime_description"].map(DETALLE).fillna("Otros: " + df["Categoría"])
    df["Gravedad"] = df["part"].map({1: "Grave", 2: "Menos grave"})   # Parte 1 / Parte 2 del FBI
    df["Arma"] = mapear(df["weapon_description"], REGLAS_ARMA, "Otra o desconocida")
    df["Lugar"] = mapear(df["premise_description"], REGLAS_LUGAR, "Otro lugar")
    df["Estado"] = df["status_description"].map(ESTADO)

    # A quién (misma limpieza del Certamen 2: H y "-" ya se pasaron a X)
    df["Sexo"] = df["victim_sex"].map({"F": "Mujer", "M": "Hombre", "X": "Desconocido (X)", "Sin dato": "Sin dato"})
    df["Edad"] = df["victim_age"].where(df["victim_age"] > 0)        # 0 o negativa = sin víctima persona
    df["Retraso (días)"] = df["retraso_dias"]

    # Indicadores 0/1: su promedio por grupo es directamente una proporción
    # (ej. mean de "Arresto" = % de casos con arresto). Evita lambdas lentas.
    df["Arresto"] = (df["Estado"] == "Con arresto").astype(int)
    df["Grave"] = (df["Gravedad"] == "Grave").astype(int)
    df["Mismo día"] = (df["Retraso (días)"] == 0).astype(int)
    df["Mujer"] = (df["Sexo"] == "Mujer").astype(float).where(df["Sexo"].isin(["Mujer", "Hombre"]))  # NaN si se desconoce

    # Coordenadas válidas: (0,0) es "ubicación faltante" según el LAPD
    df["Coord. válida"] = df["latitude"].between(33.7, 34.4) & df["longitude"].between(-118.7, -118.1)

    df = df.drop(columns=["area_name", "reporting_district", "part", "victim_sex", "victim_age",
                          "weapon_description", "premise_description", "status_description", "retraso_dias"])
    # Textos -> 'category' (enteros por dentro): 4 veces menos memoria y la copia que hace
    # st.cache_data en cada clic pasa de ~0,5 s a ~0,03 s.
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype("category")
    return df


def plano(g):
    """Pasa a texto las columnas 'category' de una tabla YA agrupada (pocas filas)."""
    return g.astype({c: str for c in g.select_dtypes("category").columns})


def contar(serie):
    """value_counts sin las categorías con 0 casos."""
    s = serie.value_counts()
    return s[s > 0]


def cruzar(filas, columnas, normalizar=False):
    """Tabla de contingencia (como pd.crosstab) solo con combinaciones observadas."""
    t = pd.DataFrame({"f": filas, "c": columnas}).groupby(["f", "c"], observed=True).size().unstack(fill_value=0)
    t.index, t.columns = t.index.astype(str), t.columns.astype(str)
    t.index.name, t.columns.name = filas.name, columnas.name
    return t.div(t.sum(axis=1), axis=0) * 100 if normalizar else t


@st.cache_data
def cargar_geojson():
    # Límites oficiales de las 21 áreas y ~1.135 distritos de reporte del LAPD
    # (fuente: LA Times "Mapping L.A." / LAPD GIS; ver README)
    with open(CARPETA / "lapd_areas.geojson") as f:
        areas = json.load(f)
    with open(CARPETA / "lapd_distritos.geojson") as f:
        distritos = json.load(f)
    km2 = {f["id"]: f["properties"]["km2"] for f in areas["features"]}
    km2_distrito = {f["id"]: f["properties"]["km2"] for f in distritos["features"]}
    return areas, distritos, km2, km2_distrito


df = cargar_datos()
GJ_AREAS, GJ_DISTRITOS, KM2, KM2_DISTRITO = cargar_geojson()

FECHA_MIN, FECHA_MAX = df["Fecha"].min().date(), df["Fecha"].max().date()
AREAS = sorted(df["Área"].unique())
CATEGORIAS = list(COLOR_CATEGORIA)
DELITOS = list(TOP10.values()) + ["Otros delitos"]
SEXOS = list(COLOR_SEXO)

# Valores por defecto de los filtros (para el botón "Restablecer")
DEFAULTS = {"f_periodo": (FECHA_MIN, FECHA_MAX), "f_areas": [], "f_categorias": [], "f_delitos": [],
            "f_gravedad": "Todos", "f_sexo": [], "f_horas": (0, 23)}
for clave, valor in DEFAULTS.items():
    st.session_state.setdefault(clave, valor)


def restablecer():
    for clave, valor in DEFAULTS.items():
        st.session_state[clave] = valor


# ── 4. SIDEBAR — FILTROS GLOBALES ────────────────────────────
# Cada widget devuelve lo que eligió el usuario. Estos filtros
# afectan a todo el dashboard: KPIs, mapas y gráficos.
with st.sidebar:
    st.title("Delitos en LA")
    st.caption("Estos filtros afectan a todos los KPIs y gráficos. Si un filtro queda vacío, se incluye todo.")

    # slider de fechas -> tupla (desde, hasta)
    fecha_ini, fecha_fin = st.slider("Período", min_value=FECHA_MIN, max_value=FECHA_MAX,
                                     format="DD/MM/YYYY", key="f_periodo")

    areas = st.multiselect("Área policial", AREAS, placeholder="Todas las áreas", key="f_areas")
    categorias = st.multiselect("Categoría de delito", CATEGORIAS, placeholder="Todas las categorías",
                                key="f_categorias")
    delitos = st.multiselect("Tipo de delito (top 10)", DELITOS, placeholder="Todos los delitos",
                             key="f_delitos")
    gravedad = st.radio("Gravedad", ["Todos", "Grave", "Menos grave"], horizontal=True, key="f_gravedad",
                        help="Clasificación del FBI que usa el LAPD: Parte 1 = grave (homicidio, robo, "
                             "agresión agravada, robo de vehículo...), Parte 2 = menos grave.")
    sexos = st.multiselect("Sexo de la víctima", SEXOS, placeholder="Todos", key="f_sexo")
    hora_ini, hora_fin = st.slider("Hora del día", 0, 23, key="f_horas", format="%d:00")

    st.button("Restablecer filtros", on_click=restablecer, width="stretch")
    st.divider()
    st.caption(f"Dataset completo: {fmt(len(df))} delitos (ene-2020 a nov-2023), sin muestreo. "
               "Fuente: LAPD vía Kaggle (asaniczka), licencia CC0.")
    st.caption(f"Versión {VERSION}. [Repositorio en GitHub]"
               "(https://github.com/jucastillobudd-svg/radiografia-delito-LA)")

# ── 5. APLICAR LOS FILTROS (pandas puro) ─────────────────────
# Máscara booleana: True en las filas que cumplen todos los filtros.
# Si una lista está vacía, no se filtra por esa variable.
mask = df["Fecha"].between(pd.Timestamp(fecha_ini), pd.Timestamp(fecha_fin))
mask &= df["Hora"].between(hora_ini, hora_fin)
if categorias:
    mask &= df["Categoría"].isin(categorias)
if delitos:
    mask &= df["Delito"].isin(delitos)
if gravedad != "Todos":
    mask &= df["Gravedad"] == gravedad
if sexos:
    mask &= df["Sexo"].isin(sexos)
mask_sin_area = mask.copy()        # la usa el comparador de áreas (pestaña Comparar áreas)
if areas:
    mask &= df["Área"].isin(areas)

dff = df[mask]  # dff = "dataframe filtrado"

# ── 6. ENCABEZADO ─────────────────────────────────────────────
# Banner con una foto de Los Ángeles (Observatorio Griffith y el centro de fondo).
# La imagen está en static/banner_la.jpg; Streamlit la sirve en "app/static/..." porque
# .streamlit/config.toml tiene enableStaticServing = true. Foto: Benjamin Cutting, Unsplash.
st.markdown("""
<div style="background-image: linear-gradient(90deg, rgba(11,37,69,.92) 0%, rgba(11,37,69,.7) 45%, rgba(11,37,69,.15) 100%), url('app/static/banner_la.jpg'); background-size: cover; background-position: center; border-radius: 8px; padding: 44px 40px; position: relative; margin-bottom: 4px">
<h1 style="color: white; margin: 0; padding: 0; max-width: 720px; line-height: 1.15">Radiografía del delito en Los Ángeles (2020–2023)</h1>
<p style="color: #dbe3ee; font-size: 1.2rem; margin: 12px 0 0; max-width: 640px">¿Dónde, cuándo y a quién debe priorizar la prevención la Policía de Los Ángeles?</p>
<span style="position: absolute; right: 12px; bottom: 6px; font-size: 0.7rem; color: rgba(255,255,255,.8)">Foto: Benjamin Cutting, Unsplash</span>
</div>
""", unsafe_allow_html=True)
st.caption("Dirigido a las jefaturas de área y equipos de planificación de patrullajes del LAPD, "
           "y a la Municipalidad de Los Ángeles. "
           f"Con los filtros aplicados se muestran {fmt(len(dff))} de {fmt(len(df))} delitos.")

# Si los filtros dejan el DataFrame vacío, avisamos y paramos.
if dff.empty:
    st.warning("No hay delitos para los filtros seleccionados. Ajusta el panel lateral "
               "o usa el botón Restablecer filtros.")
    st.stop()

# ── 7. KPIs (TARJETAS DE MÉTRICAS) ───────────────────────────
# delta = comparación contra el total sin filtros (df), no contra dff.
dias_sel = (pd.Timestamp(fecha_fin) - pd.Timestamp(fecha_ini)).days + 1
dias_tot = (df["Fecha"].max() - df["Fecha"].min()).days + 1
# El promedio de una columna 0/1 es una proporción (ver sección 3)
kpi = {c: dff[col].mean() * 100 for c, col in
       [("grave", "Grave"), ("arresto", "Arresto"), ("mujer", "Mujer"), ("mismo_dia", "Mismo día")]}
kpi_tot = {c: df[col].mean() * 100 for c, col in
           [("grave", "Grave"), ("arresto", "Arresto"), ("mujer", "Mujer"), ("mismo_dia", "Mismo día")]}
kpi["mujer"] = 0 if pd.isna(kpi["mujer"]) else kpi["mujer"]
por_hora = dff.loc[dff["Hora"] != 12, "Hora"].value_counts()   # sin las 12:00 (hora por defecto)


def delta_pp(clave):
    return f"{kpi[clave] - kpi_tot[clave]:+.1f} pp vs total".replace(".", ",")


k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Delitos", fmt(len(dff)), delta=f"{pct(len(dff) / len(df) * 100)} del total", delta_color="off",
          help="Cantidad de delitos con los filtros aplicados y su % sobre el total sin filtros.")
k2.metric("Promedio diario", num(len(dff) / dias_sel), delta=f"total: {num(len(df) / dias_tot)}/día",
          delta_color="off", help="Delitos por día dentro del período elegido.")
k3.metric("Delitos graves", pct(kpi["grave"]), delta=delta_pp("grave"), delta_color="inverse",
          help="% de delitos Parte 1 (FBI). Rojo = la selección es más grave que el total.")
k4.metric("Con arresto", pct(kpi["arresto"]), delta=delta_pp("arresto"),
          help="% de casos cerrados con arresto (adulto o menor). Verde = más arrestos que el total.")
k5.metric("Víctimas mujeres", pct(kpi["mujer"]), delta=delta_pp("mujer"), delta_color="off",
          help="% de mujeres entre las víctimas con sexo conocido (mujer u hombre).")
k6.metric("Hora más crítica", f"{por_hora.index[0]}:00" if len(por_hora) else "Sin dato",
          delta=f"{pct(kpi['mismo_dia'], 0)} mismo día", delta_color="off",
          help="Hora con más delitos, sin contar las 12:00 (hora que se anota por defecto cuando no se "
               "conoce la real). Debajo: % de delitos denunciados el mismo día en que ocurrieron.")

st.divider()

# ── PESTAÑAS ─────────────────────────────────────────────────
tab_donde, tab_que, tab_quien, tab_cuando, tab_comparar, tab_hallazgos = st.tabs(
    ["Dónde", "Qué", "A quién", "Cuándo", "Comparar áreas", "Hallazgos"])

# Datos para los mapas: solo coordenadas válidas
dff_mapa = dff[dff["Coord. válida"]]
invalidas = len(dff) - len(dff_mapa)
centro = ({"lat": dff_mapa["latitude"].mean(), "lon": dff_mapa["longitude"].mean()}
          if areas and len(dff_mapa) else CENTRO_LA)
zoom = 10.6 if areas else 9.1

# Capa con los bordes de las 21 áreas: se dibuja encima de los mapas
# de puntos y densidad para que se lean los límites policiales.
BORDES = [dict(sourcetype="geojson", source=GJ_AREAS, type="line", color="#1b1b1b", line=dict(width=1.2))]

# ── 8. PESTAÑA DÓNDE — MAPAS ─────────────────────────────────
with tab_donde:
    st.caption(f"Se excluyeron {fmt(invalidas)} delitos ({pct(invalidas / len(dff) * 100, 2)}) con "
               "coordenadas inválidas: (0,0), que el LAPD usa cuando falta la ubicación, o puntos fuera de "
               "Los Ángeles (latitud 33,7 a 34,4 y longitud -118,7 a -118,1).")

    # ---- 8.1 Coropleta por área o distrito --------------------
    st.subheader("Mapa de coropletas: ¿qué zonas concentran el delito?")
    c1, c2, c3 = st.columns([1.2, 1.6, 1])
    # Controles locales: solo afectan a este mapa
    nivel = c1.radio("Nivel geográfico", ["Área (21)", "Distrito de reporte (~1.100)"], horizontal=True,
                     key="cor_nivel")
    indicador = c2.selectbox("Indicador", ["Delitos", "Delitos por km² al año", "% delitos graves", "% con arresto",
                                           "Variación del promedio diario (primer vs último año)"], key="cor_ind")
    estilo = c3.selectbox("Mapa base", list(ESTILOS_MAPA), key="cor_estilo")

    # Misma lógica para los dos niveles: solo cambian la columna, el GeoJSON y los km²
    unidad = "Área" if nivel.startswith("Área") else "Distrito"
    geojson = GJ_AREAS if unidad == "Área" else GJ_DISTRITOS
    km2_unidad = KM2 if unidad == "Área" else KM2_DISTRITO

    col_mapa, col_texto = st.columns([3, 1.1])
    g = plano(dff_mapa.groupby(unidad, observed=True)
              .agg(Delitos=("Grave", "size"), Graves=("Grave", "mean"), Arresto=("Arresto", "mean"),
                   Área_=("Área", "first"))
              .reset_index())
    g[["Graves", "Arresto"]] *= 100
    if unidad == "Distrito":
        g["Área"] = g.pop("Área_")
    else:
        g = g.drop(columns="Área_")
    # Delito más frecuente de cada zona: contar (zona, delito) y quedarse con el mayor
    principal = (dff_mapa.groupby([unidad, "Delito (detalle)"], observed=True).size()
                 .sort_values(ascending=False).reset_index().drop_duplicates(unidad))
    g["Principal"] = g[unidad].map(dict(zip(plano(principal)[unidad], plano(principal)["Delito (detalle)"])))
    g["Buró"] = g["Área"].map(BURO)
    g["km²"] = g[unidad].map(km2_unidad)
    g["Delitos por km² al año"] = g["Delitos"] / g["km²"] / max(dias_sel / 365.25, 1 / 365.25)

    # Variación: promedio diario del primer año vs el último año de la selección
    a1, a2 = int(dff["Año"].min()), int(dff["Año"].max())
    rango = dff.groupby("Año")["Fecha"].agg(["min", "max"])
    dias_por_anio = (rango["max"] - rango["min"]).dt.days + 1
    por_anio = dff_mapa.groupby([unidad, "Año"], observed=True).size().unstack(fill_value=0)
    if a1 != a2:
        base_a1 = por_anio[a1].where(por_anio[a1] >= 20)          # con menos de 20 casos el % no es confiable
        variacion = ((por_anio[a2] / dias_por_anio[a2]) / (base_a1 / dias_por_anio[a1]) - 1) * 100
        g["Variación"] = g[unidad].map(dict(zip(variacion.index.astype(g[unidad].dtype), variacion)))
    else:
        g["Variación"] = float("nan")
    g = g.rename(columns={"Graves": "% delitos graves", "Arresto": "% con arresto"})

    columna_color = "Variación" if indicador.startswith("Variación") else indicador
    if columna_color == "Variación" and a1 == a2:
        st.warning("La variación necesita al menos dos años en el período: amplía el filtro de fechas.")
        columna_color = "Delitos"
    diverge = columna_color == "Variación"
    # Rango de color: con ~1.100 distritos, unos pocos extremos dejarían el resto pálido
    if diverge:
        tope = g["Variación"].abs().quantile(0.95)
        rango_color = [-tope, tope]
    elif unidad == "Distrito" and columna_color in ("Delitos", "Delitos por km² al año"):
        rango_color = [0, g[columna_color].quantile(0.98)]
    else:
        rango_color = None
    fig = px.choropleth_map(
        g, geojson=geojson, locations=unidad, color=columna_color,
        hover_name=unidad,
        hover_data={unidad: False, "Área": unidad == "Distrito", "Buró": True, "Delitos": ":,",
                    "Delitos por km² al año": ":,.0f", "% delitos graves": ":.1f", "% con arresto": ":.1f",
                    "Variación": ":+.1f", "Principal": True, "km²": ":.2f"},
        labels={"Principal": "Delito más frecuente", "Variación": f"Variación {a1}-{a2} (%)",
                "Distrito": "Distrito de reporte"},
        color_continuous_scale="RdBu_r" if diverge else "Reds",
        range_color=rango_color,
        map_style=ESTILOS_MAPA[estilo], center=centro, zoom=zoom, opacity=0.65 if unidad == "Área" else 0.75,
    )
    fig.update_traces(marker_line_width=0.8 if unidad == "Área" else 0.2)
    fig.update_layout(**LAYOUT)
    fig.update_layout(height=600, margin=dict(t=10, b=0, l=0, r=0),
                      coloraxis_colorbar=dict(title=columna_color.replace(" (primer vs último año)", ""),
                                              thickness=12, len=0.7))
    col_mapa.plotly_chart(fig, width="stretch")

    with col_texto:
        orden = g.sort_values(columna_color, ascending=False).dropna(subset=[columna_color])
        nombre = unidad
        top3 = ", ".join(f"{r[nombre]} ({num(r[columna_color], 1 if '%' in columna_color or columna_color == 'Variación' else 0)})"
                         for _, r in orden.head(3).iterrows())
        bajo = orden.iloc[-1]
        st.markdown(f"##### Lectura del mapa")
        if unidad == "Área":
            top5 = g.nlargest(5, "Delitos")["Delitos"].sum() / g["Delitos"].sum() * 100
            extra = f"Las 5 áreas con más delitos suman el {pct(top5)} del total."
        else:
            top10 = g.nlargest(max(round(len(g) * 0.1), 1), "Delitos")["Delitos"].sum() / g["Delitos"].sum() * 100
            extra = f"El 10% de los distritos con más delitos reúne el {pct(top10)} de los casos."
        st.markdown(f"Dónde se concentra: {top3}. {extra}")
        if len(orden) > 1:
            st.markdown(f"Dónde no: {bajo[nombre]} tiene el valor más bajo "
                        f"({num(bajo[columna_color], 1 if '%' in columna_color or columna_color == 'Variación' else 0)}).")
        else:
            st.markdown("Dónde no: con una sola zona en el mapa no hay con qué comparar; "
                        "quita el filtro de área o cambia a nivel distrito.")
        st.markdown("Qué implica: para priorizar el patrullaje conviene mirar la densidad (delitos por km²) "
                    "además de la cantidad, porque un área grande del Valle puede sumar muchos delitos repartidos "
                    "en mucho territorio, mientras que en Central (Downtown) se juntan en pocas cuadras.")

    st.divider()

    # ---- 8.2 Mapa de puntos + 8.3 mapa de densidad ------------
    col_p, col_d = st.columns(2)
    with col_p:
        st.subheader("Mapa de puntos: cada delito")
        p1, p2 = st.columns(2)
        color_pts = p1.selectbox("Colorear por", ["Gravedad", "Categoría", "Sexo", "Arma", "Lugar"], key="pts_color")
        n_pts = p2.select_slider("Puntos en el mapa", [5_000, 10_000, 25_000, 50_000, 100_000], value=10_000,
                                 key="pts_n", help="Con más de 100 mil puntos el navegador se pone lento: "
                                                   "se usa una muestra aleatoria reproducible (random_state=42).")
        cols_pts = ["latitude", "longitude", "date_occurred", "Delito (detalle)", "Área", "Lugar", "Arma",
                    "Edad", "Sexo"] + ([color_pts] if color_pts not in ("Lugar", "Arma", "Sexo") else [])
        muestra = plano(dff_mapa[cols_pts].sample(min(len(dff_mapa), n_pts), random_state=42))
        colores = {"Gravedad": COLOR_GRAVEDAD, "Categoría": COLOR_CATEGORIA, "Sexo": COLOR_SEXO}.get(color_pts)
        fig = px.scatter_map(
            muestra, lat="latitude", lon="longitude", color=color_pts,
            color_discrete_map=colores, color_discrete_sequence=SECUENCIA,
            hover_name="Delito (detalle)",
            hover_data={"latitude": False, "longitude": False, "date_occurred": "|%d/%m/%Y %H:%M",
                        "Área": True, "Lugar": True, "Arma": True, "Edad": True, "Sexo": True},
            labels={"date_occurred": "Fecha y hora", "Edad": "Edad víctima"},
            map_style=ESTILOS_MAPA[estilo], center=centro, zoom=zoom, opacity=0.55,
        )
        fig.update_traces(marker_size=5)
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=520, margin=dict(t=0, b=0, l=0, r=0), map_layers=BORDES,
                          legend=dict(orientation="h", y=-0.02, title=""))
        st.plotly_chart(fig, width="stretch")
        st.caption(f"Muestra de {fmt(len(muestra))} de {fmt(len(dff_mapa))} delitos con coordenadas válidas "
                   "(random_state=42). Líneas negras = límites de las 21 áreas.")
        mayor = muestra.groupby("Área").size().idxmax() if len(muestra) else "sin datos"
        lectura(f"Dónde se concentra: el área con más puntos en la muestra es {mayor}. Con todos los datos, los "
                "puntos se juntan en el centro-sur (Downtown, Koreatown, Hollywood y South LA) y siguen las avenidas "
                "del Valle.\n\nDónde no: los cerros (Santa Monica Mountains y Griffith Park) casi no tienen puntos."
                "\n\nQué implica: si se colorea por Categoría, los delitos de vehículo aparecen repartidos por toda "
                "la ciudad y necesitan cobertura amplia, mientras que la violencia se concentra en el centro-sur y "
                "permite un patrullaje más focalizado.")

    with col_d:
        st.subheader("Mapa de densidad: puntos calientes")
        d1, d2 = st.columns(2)
        celda = d1.radio("Tamaño de celda", ["~1 km", "~500 m"], horizontal=True, key="den_celda")
        radio = d2.slider("Radio de suavizado", 5, 40, 14 if not areas else 22, key="den_radio")
        paso = 100 if celda == "~1 km" else 200          # 1/100 de grado ≈ 1 km ; 1/200 ≈ 500 m
        # Agrupar por celda (como en el Certamen 2): con 850 mil puntos el mapa se satura
        lat_celda = ((dff_mapa["latitude"] * paso).round() / paso).rename("lat")
        lon_celda = ((dff_mapa["longitude"] * paso).round() / paso).rename("lon")
        g = plano(dff_mapa.groupby([lat_celda, lon_celda])
                  .agg(Delitos=("Grave", "size"), Área=("Área", "first")).reset_index())
        fig = px.density_map(
            g, lat="lat", lon="lon", z="Delitos", radius=radio,
            hover_data={"lat": False, "lon": False, "Área": True, "Delitos": ":,"},
            color_continuous_scale="YlOrRd", range_color=[0, g["Delitos"].quantile(0.99)],
            map_style=ESTILOS_MAPA[estilo], center=centro, zoom=zoom,
        )
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=520, margin=dict(t=0, b=0, l=0, r=0), map_layers=BORDES,
                          coloraxis_colorbar=dict(title="Delitos<br>por celda", thickness=12, len=0.6))
        st.plotly_chart(fig, width="stretch")
        top_celda = g.nlargest(1, "Delitos").iloc[0]
        st.caption(f"{fmt(len(g))} celdas de {celda}. Escala hasta el percentil 99 para que pocas celdas "
                   "extremas no dejen el resto pálido.")
        lectura(f"Dónde se concentra: la celda con más delitos está en {top_celda['Área']} "
                f"({fmt(top_celda['Delitos'])}). Con todos los datos, de las 15 celdas con más delitos 8 están en "
                "Central (Downtown), 3 en Olympic (Koreatown), 2 en Hollywood y 2 en Rampart.\n\nDónde no: la "
                f"mediana es de {fmt(g['Delitos'].median())} delitos por celda y en el Valle los focos son chicos y "
                "dispersos.\n\nQué implica: el delito se junta en manchas de pocas cuadras, así que conviene "
                "asignar patrullaje a esos puntos calientes en vez de repartirlo parejo por toda el área.")

    st.divider()

    # ---- 8.4 Ranking de áreas ---------------------------------
    st.subheader("Ranking de áreas")
    r1, _ = st.columns([2, 3])
    orden_rank = r1.radio("Ordenar por", ["Cantidad de delitos", "Delitos por km² al año"], horizontal=True,
                          key="rank_orden")
    g = plano(dff.groupby("Área", observed=True).size().reset_index(name="Delitos"))
    g["Buró"] = g["Área"].map(BURO)
    g["km²"] = g["Área"].map(KM2)
    g["Delitos por km² al año"] = g["Delitos"] / g["km²"] / max(dias_sel / 365.25, 1 / 365.25)
    g["% del total"] = g["Delitos"] / g["Delitos"].sum() * 100
    x = "Delitos" if orden_rank.startswith("Cantidad") else "Delitos por km² al año"
    g = g.sort_values(x)
    fig = px.bar(g, x=x, y="Área", orientation="h", color="Buró", color_discrete_map=COLOR_BURO,
                 category_orders={"Buró": list(COLOR_BURO)}, hover_name="Área",
                 hover_data={"Área": False, "Delitos": ":,", "% del total": ":.1f", "km²": ":.1f",
                             "Delitos por km² al año": ":,.0f"},
                 text=g[x].map(lambda v: fmt(v)))
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(**LAYOUT)
    fig.update_layout(height=max(320, 26 * len(g)), yaxis=dict(title="", categoryorder="array",
                                                                 categoryarray=list(g["Área"])),
                      xaxis_title="Delitos" if x == "Delitos" else "Delitos por km² al año",
                      legend=dict(orientation="h", y=-0.12, title="Buró"))
    st.plotly_chart(fig, width="stretch")
    lectura("Por cantidad, Central, 77th Street y Pacific están arriba y las diferencias entre áreas son moderadas. "
            "Por densidad el orden cambia bastante: Central (1.157 delitos por km² al año con todos los datos) más "
            "que duplica a todas las áreas salvo Rampart y Olympic, y las áreas del Valle y West LA quedan al final "
            "porque sus delitos están repartidos en mucho territorio.")

# ── 9. PESTAÑA QUÉ — JERARQUÍA DE DELITOS ────────────────────
with tab_que:
    st.subheader("¿Qué delitos ocurren? Vista jerárquica")
    q1, q2, q3 = st.columns(3)
    tipo_jer = q1.radio("Gráfico", ["Sunburst", "Treemap"], horizontal=True, key="jer_tipo")
    jerarquias = {
        "Categoría → Delito": ["Categoría", "Delito (detalle)"],
        "Gravedad → Categoría → Delito": ["Gravedad", "Categoría", "Delito (detalle)"],
        "Buró → Área → Categoría": ["Buró", "Área", "Categoría"],
        "Categoría → Lugar → Arma": ["Categoría", "Lugar", "Arma"],
    }
    jer = q2.selectbox("Jerarquía (path)", list(jerarquias), key="jer_path")
    colores_jer = {"% con arresto": "Arresto", "% víctimas mujeres": "Mujer", "Edad mediana de la víctima": "Edad",
                   "% denunciado el mismo día": "Mismo día"}
    color_jer = q3.selectbox("Color (continuo)", list(colores_jer), key="jer_color")

    path = jerarquias[jer]
    col = colores_jer[color_jer]
    # Una fila por combinación del path: cantidad (values) + indicador para el color
    g = plano(dff.groupby(path, observed=True)
              .agg(Delitos=("Grave", "size"), Valor=(col, "median" if col == "Edad" else "mean"))
              .reset_index().rename(columns={"Valor": col}))
    if col != "Edad":
        g[col] *= 100
    g = g.dropna(subset=[col])
    g = g.rename(columns={col: color_jer})
    funcion = px.sunburst if tipo_jer == "Sunburst" else px.treemap
    fig = funcion(
        g, path=path, values="Delitos", color=color_jer,
        hover_data={"Delitos": ":,", color_jer: ":.1f"},
        # % mujeres: escala divergente centrada en 50% (paridad); el resto: escala secuencial
        color_continuous_scale="RdBu_r" if col == "Mujer" else "Reds",
        color_continuous_midpoint=50 if col == "Mujer" else None,
    )
    fig.update_traces(textinfo="label+percent parent")
    if tipo_jer == "Sunburst":
        fig.update_traces(insidetextorientation="radial")
    fig.update_layout(**LAYOUT)
    fig.update_layout(height=640, margin=dict(t=10, b=10, l=10, r=10),
                      coloraxis_colorbar=dict(title=color_jer, thickness=12))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"`path = {path}`, `values = 'Delitos'` (cantidad de delitos), color = {color_jer.lower()} "
               "(los niveles superiores muestran el promedio ponderado). Haz clic en un sector para entrar "
               "y en el centro para volver.")
    lectura("Violencia y amenazas es la categoría más grande (30,5% con todos los datos), seguida de Vehículos "
            "(26,0%). Todos los delitos de vehículo y de robo son graves (Parte 1). Con el color en % con arresto, "
            "la violencia es la más oscura (17,6% termina en arresto), mientras que Vehículos (2,6%) y Fraude (1,7%) "
            "casi no tienen color. Con el color en % víctimas mujeres (rojo = mayoría mujeres), destacan la violencia "
            "de pareja, los delitos sexuales y el robo de identidad.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        # Univariado categórico: los 15 delitos más frecuentes
        st.subheader("Los 15 delitos más frecuentes")
        g = plano(dff.groupby(["Delito (detalle)", "Categoría"], observed=True).size()
                  .reset_index(name="Delitos").rename(columns={"Delito (detalle)": "Delito"}))
        g = g[~g["Delito"].str.startswith("Otros")].nlargest(15, "Delitos").sort_values("Delitos")
        g["% de la selección"] = g["Delitos"] / len(dff) * 100
        fig = px.bar(g, x="Delitos", y="Delito", orientation="h", color="Categoría",
                     color_discrete_map=COLOR_CATEGORIA, hover_name="Delito",
                     hover_data={"Delito": False, "Delitos": ":,", "% de la selección": ":.1f"})
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=520, yaxis=dict(title="", categoryorder="array", categoryarray=list(g["Delito"])),
                          xaxis_title="Cantidad de delitos", legend=dict(orientation="h", y=-0.15, title=""))
        st.plotly_chart(fig, width="stretch")
    with c2:
        # ¿Cómo terminan los casos? Estado por categoría (barras 100%)
        st.subheader("¿Cómo terminan los casos?")
        conteo = cruzar(dff["Categoría"], dff["Estado"])
        tabla = conteo.div(conteo.sum(axis=1), axis=0) * 100
        tabla = tabla.reindex(columns=[c for c in ESTADOS if c in tabla.columns])
        tabla = tabla.sort_values("Con arresto") if "Con arresto" in tabla else tabla
        g = tabla.reset_index().melt(id_vars="Categoría", var_name="Estado", value_name="Porcentaje")
        g["Casos"] = g["Categoría"].map(conteo.sum(axis=1))
        g["Etiqueta"] = g["Porcentaje"].round(0).astype(int).astype(str).where(g["Porcentaje"] >= 5, "")
        fig = px.bar(g, x="Porcentaje", y="Categoría", color="Estado", orientation="h", text="Etiqueta",
                     color_discrete_map=COLOR_ESTADO, category_orders={"Categoría": list(tabla.index),
                                                                         "Estado": ESTADOS},
                     hover_name="Categoría",
                     hover_data={"Categoría": False, "Porcentaje": ":.1f", "Casos": ":,"},
                     labels={"Porcentaje": "% de los casos de la categoría"})
        fig.update_traces(offsetgroup="1", textangle=0, insidetextanchor="middle")
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=520, yaxis_title="", legend=dict(orientation="h", y=-0.15, title=""))
        st.plotly_chart(fig, width="stretch")
    lectura("A la izquierda están los 15 delitos más frecuentes, encabezados por el robo de vehículo. A la derecha "
            "está el estado de los casos: 8 de cada 10 siguen en investigación y solo la violencia supera el 15% de "
            "arrestos. En vehículos y fraude casi no hay arrestos.")

    # Relación entre dos variables categóricas: lugar x categoría (ancho completo)
    st.subheader("¿Dónde ocurre cada tipo de delito?")
    tabla = cruzar(dff["Categoría"], dff["Lugar"], normalizar=True)      # cada fila suma 100
    tabla = tabla.reindex([c for c in CATEGORIAS if c in tabla.index])
    tabla = tabla.reindex(columns=[c for c in LUGARES if c in tabla.columns])
    tabla = tabla.loc[:, tabla.max() >= 0.5]                              # sin columnas vacías
    tabla.columns = [c.replace(" o ", " o<br>").replace(" y ", " y<br>") for c in tabla.columns]  # 2 líneas
    fig = px.imshow(tabla.round(1), text_auto=".0f", aspect="auto", color_continuous_scale="Reds",
                    labels=dict(x="Lugar", y="Categoría", color="% de la categoría"))
    fig.update_traces(hovertemplate="<b>%{y}</b> en <b>%{x}</b><br>%{z:.1f}% de los delitos de la "
                                    "categoría<extra></extra>")
    fig.update_layout(**LAYOUT)
    fig.update_layout(height=430, xaxis=dict(title="", side="top", tickangle=0), yaxis_title="")
    st.plotly_chart(fig, width="stretch")
    lectura("Cada fila suma 100%. Los delitos de vehículo ocurren sobre todo en la calle (62%) y en estacionamientos. "
            "El fraude (70%) y los delitos sexuales (57%) ocurren principalmente en la vivienda. La violencia se "
            "reparte entre vivienda (39%) y calle (35%), y el robo y hurto entre vivienda (39%) y comercio. Esto "
            "sirve para decidir qué tipo de unidad patrulla en cada lugar.")

# ── 10. PESTAÑA A QUIÉN — VÍCTIMAS ───────────────────────────
with tab_quien:
    # Solo delitos con víctima persona (edad > 0) y solo las columnas que se usan aquí
    dff_persona = dff.loc[dff["Edad"].notna(),
                          ["Edad", "Sexo", "Gravedad", "Categoría", "Delito", "Delito (detalle)", "Área", "Buró",
                           "Lugar", "Arma", "Tipo de día", "Estado", "Hora", "N° día", "Mes del año",
                           "Retraso (días)"]]
    if dff_persona.empty:
        st.info("La selección no incluye delitos con víctima persona (el robo de vehículo casi nunca la tiene).")
    else:
        c1, c2 = st.columns(2)
        with c1:
            # Univariado numérico: histograma de edad
            st.subheader("Edad de las víctimas")
            separar = st.selectbox("Separar por", ["Nada", "Sexo", "Gravedad", "Categoría"], key="hist_sep")
            sep = [] if separar == "Nada" else [separar]
            datos_hist = dff_persona if separar != "Sexo" else dff_persona[dff_persona["Sexo"].isin(["Mujer", "Hombre"])]
            # Se cuenta por edad en pandas y Plotly solo dibuja ~100 filas (no 640 mil)
            conteo = plano(datos_hist.groupby(["Edad"] + sep, observed=True).size().reset_index(name="Víctimas"))
            fig = px.histogram(conteo, x="Edad", y="Víctimas", histfunc="sum", color=sep[0] if sep else None,
                               nbins=45, barmode="overlay", opacity=0.75,
                               color_discrete_map={**COLOR_SEXO, **COLOR_GRAVEDAD, **COLOR_CATEGORIA},
                               color_discrete_sequence=[AZUL],
                               labels={"Edad": "Edad de la víctima (años)"})
            fig.update_traces(hovertemplate="Edad %{x} años<br>%{y:,} víctimas<extra>%{fullData.name}</extra>")
            mediana = dff_persona["Edad"].median()
            fig.add_vline(x=mediana, line_dash="dash", line_color=ROJO,
                          annotation_text=f"Mediana {mediana:.0f} años", annotation_position="top right")
            fig.update_layout(**LAYOUT)
            fig.update_layout(height=430, yaxis_title="Víctimas", legend=dict(orientation="h", y=-0.2, title=""))
            st.plotly_chart(fig, width="stretch")
            lectura(f"La distribución tiene asimetría positiva. La mediana es {mediana:.0f} años y la cola llega a más "
                    "de 90. La mayor cantidad de víctimas tiene entre 25 y 40 años. Se excluyen las edades 0 o "
                    "negativas, que corresponden a delitos sin víctima persona (por ejemplo, robo de vehículo).")
        with c2:
            # Relación categórica-numérica: edad por delito
            st.subheader("Edad según tipo de delito")
            eje = st.selectbox("Agrupar por", ["Delito", "Categoría", "Área"], key="box_eje")
            datos_box = dff_persona if eje != "Delito" else dff_persona[dff_persona["Delito"] != "Otros delitos"]
            if datos_box.empty:      # ej. filtro "Delitos sexuales": ninguno está en el top 10
                eje, datos_box = "Categoría", dff_persona
                st.caption("Ningún delito del top 10 en la selección: se agrupa por categoría.")
            orden = datos_box.groupby(eje, observed=True)["Edad"].median().sort_values()
            orden.index = orden.index.astype(str)
            muestra = plano(datos_box[["Edad", eje]].sample(min(len(datos_box), 30_000), random_state=42))
            fig = px.box(muestra, x="Edad", y=eje, points=False, color_discrete_sequence=[AZUL],
                         category_orders={eje: list(orden.index)},
                         hover_data={"Edad": True},
                         labels={"Edad": "Edad de la víctima (años)", eje: ""})
            fig.update_layout(**LAYOUT)
            fig.update_layout(height=430 + 6 * max(0, len(orden) - 10))
            st.plotly_chart(fig, width="stretch")
            lectura(f"La mediana va desde {orden.iloc[0]:.0f} años ({orden.index[0]}) hasta "
                    f"{orden.iloc[-1]:.0f} ({orden.index[-1]}). El gráfico usa una muestra de 30 mil víctimas "
                    "(random_state=42) para que cargue rápido, pero las medianas se calculan con todos los datos.")

        st.divider()
        st.subheader("Sexo de la víctima por delito")
        conteo = cruzar(dff_persona["Delito (detalle)"], dff_persona["Sexo"])
        conteo = conteo[~conteo.index.str.startswith("Otros")]
        n_delito = conteo.sum(axis=1).nlargest(15)                       # los 15 delitos con más víctimas
        tabla = (conteo.loc[n_delito.index].div(n_delito, axis=0) * 100)   # % por fila (suma 100)
        tabla = tabla.reindex(columns=SEXOS, fill_value=0).sort_values("Mujer")
        g = tabla.reset_index().melt(id_vars="Delito (detalle)", var_name="Sexo", value_name="Porcentaje")
        g["Víctimas"] = g["Delito (detalle)"].map(n_delito)
        g["Etiqueta"] = g["Porcentaje"].round(0).astype(int).astype(str).where(g["Porcentaje"] >= 4, "")
        fig = px.bar(g, x="Porcentaje", y="Delito (detalle)", color="Sexo", orientation="h", text="Etiqueta",
                     barmode="stack", color_discrete_map=COLOR_SEXO,
                     category_orders={"Delito (detalle)": list(tabla.index), "Sexo": SEXOS},
                     hover_name="Delito (detalle)",
                     hover_data={"Delito (detalle)": False, "Porcentaje": ":.1f", "Víctimas": ":,"},
                     labels={"Porcentaje": "% de las víctimas", "Delito (detalle)": ""})
        fig.update_traces(offsetgroup="1", textangle=0, insidetextanchor="middle")   # apilar al 100%
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=520, legend=dict(orientation="h", y=-0.12, title=""))
        st.plotly_chart(fig, width="stretch")
        mas_mujer, mas_hombre = tabla["Mujer"].idxmax(), tabla["Hombre"].idxmax()
        lectura(f"El delito con mayor proporción de víctimas mujeres es {mas_mujer} ({tabla.loc[mas_mujer, 'Mujer']:.0f}%) "
                f"y el con mayor proporción de hombres es {mas_hombre} ({tabla.loc[mas_hombre, 'Hombre']:.0f}%). Como "
                "el perfil de la víctima cambia según el delito, la prevención debería ajustarse a cada uno.")

        st.divider()
        # ---- Multidimensional 1: categorías paralelas -----------
        st.subheader("Categorías paralelas: cómo se combinan gravedad, delito, lugar, arma y víctima")
        dims_pc = st.multiselect("Dimensiones (en orden)", ["Gravedad", "Categoría", "Lugar", "Arma", "Sexo",
                                                            "Tipo de día", "Estado", "Buró"],
                                 default=["Gravedad", "Categoría", "Lugar", "Arma", "Sexo"], key="pcat_dims",
                                 max_selections=6)
        if len(dims_pc) < 2:
            st.info("Elige al menos 2 dimensiones.")
        else:
            muestra = plano(dff_persona[dims_pc + ["Edad"]].sample(min(len(dff_persona), 20_000), random_state=42))
            # Edad redondeada a la década: con la edad exacta cada víctima sería una cinta distinta
            muestra["Edad (década)"] = (muestra["Edad"] // 10 * 10).clip(upper=80)
            fig = px.parallel_categories(muestra, dimensions=dims_pc, color="Edad (década)",
                                         color_continuous_scale="Viridis_r",
                                         labels={"Edad (década)": "Edad de la víctima"})
            fig.update_traces(hoveron="color", hoverinfo="count+probability",
                              hovertemplate="<b>%{category}</b><br>Víctimas en la muestra: %{count:,}"
                                            "<br>Proporción: %{probability:.1%}<extra></extra>",
                              line_shape="hspline", labelfont=dict(size=13, color="#1b1b1b"),
                              tickfont=dict(size=11, color="#333"))
            fig.update_layout(**LAYOUT)
            fig.update_layout(height=560, margin=dict(t=40, b=30, l=140, r=140),
                              coloraxis_colorbar=dict(title="Edad", thickness=12))
            st.plotly_chart(fig, width="stretch")
            lectura("Cada cinta es un grupo de víctimas. El ancho indica la cantidad y el color la edad por década "
                    "(amarillo = joven, morado = mayor). Siguiendo las cintas de izquierda a derecha, los delitos "
                    "graves con víctima se reparten entre vivienda (35%) y calle (33%), la fuerza física es el 55% "
                    "de los casos con arma, y en "
                    "todas las categorías las víctimas mujeres son algo más jóvenes (en delitos sexuales, mediana de "
                    "27 años frente a 33 en hombres). Al hacer clic en una categoría se resalta. Muestra de 20 mil "
                    "(random_state=42).")

        # ---- Multidimensional 2: coordenadas paralelas ----------
        st.subheader("Coordenadas paralelas: edad, hora, día y retraso de la denuncia")
        color_pc = st.selectbox("Color continuo", ["Edad", "Hora", "Retraso (días)"], key="pcoord_color")
        # Solo denuncias hechas hasta 30 días después del delito (vista 0–30 días como en el Certamen 2)
        hasta30 = dff_persona[dff_persona["Retraso (días)"] <= 30]
        muestra = hasta30[["Edad", "Hora", "N° día", "Mes del año", "Retraso (días)"]].sample(
            min(len(hasta30), 5_000), random_state=42)
        fig = px.parallel_coordinates(
            muestra, dimensions=["Edad", "Hora", "N° día", "Mes del año", "Retraso (días)"], color=color_pc,
            color_continuous_scale="Plasma_r",
            labels={"Edad": "Edad (años)", "Hora": "Hora (0–23)", "N° día": "Día (1=lun, 7=dom)",
                    "Mes del año": "Mes (1–12)", "Retraso (días)": "Retraso denuncia (días, hasta 30)"},
        )
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=480, margin=dict(t=70, b=30, l=60, r=60),
                          coloraxis_colorbar=dict(title=color_pc, thickness=12))
        st.plotly_chart(fig, width="stretch")
        lectura("Arrastrando el mouse sobre un eje se filtran las líneas (por ejemplo, Retraso mayor a 20 días). Las "
                "denuncias tardías tienen edades parecidas al resto, pero son sobre todo fraude y robo de identidad "
                "(40% de ellas, con todos los datos), y casi 1 de cada 5 tiene la hora en 12:00, porque si la víctima "
                "se entera días después no sabe a qué hora ocurrió. Se muestran las denuncias hechas hasta 30 días "
                f"después del delito ({pct(len(hasta30) / len(dff_persona) * 100)} de las víctimas) y una muestra de "
                "5 mil (random_state=42), porque con más líneas el gráfico no se lee.")

# ── 11. PESTAÑA CUÁNDO — TIEMPO ──────────────────────────────
with tab_cuando:
    st.subheader("Delitos por mes y contexto de la pandemia")
    separar = st.selectbox("Separar la línea por", ["Total", "Categoría", "Gravedad", "Área (top 5)",
                                                    "Tipo de delito (top 5)"], key="linea_sep")
    if separar == "Total":
        g = dff.groupby("Mes").size().reset_index(name="Delitos")
        fig = px.line(g, x="Mes", y="Delitos", markers=True, color_discrete_sequence=[AZUL],
                      hover_data={"Mes": "|%m/%Y", "Delitos": ":,"})
    else:
        col = {"Área (top 5)": "Área", "Tipo de delito (top 5)": "Delito"}.get(separar, separar)
        top = contar(dff[col]).drop("Otros delitos", errors="ignore").head(5 if "top" in separar else 10).index.astype(str)
        g = plano(dff[dff[col].isin(top)].groupby(["Mes", col], observed=True).size().reset_index(name="Delitos"))
        fig = px.line(g, x="Mes", y="Delitos", color=col, category_orders={col: list(top)},
                      color_discrete_map={**COLOR_CATEGORIA, **COLOR_GRAVEDAD}, color_discrete_sequence=SECUENCIA,
                      hover_data={"Mes": "|%m/%Y", "Delitos": ":,"})
    # Hitos de la pandemia (solo si caen dentro del período elegido)
    ini, fin = pd.Timestamp(fecha_ini), pd.Timestamp(fecha_fin)
    if ini <= pd.Timestamp("2021-06-15") and fin >= pd.Timestamp("2020-03-19"):
        fig.add_vrect(x0=max(pd.Timestamp("2020-03-19"), ini), x1=min(pd.Timestamp("2021-06-15"), fin),
                      fillcolor=GRIS, opacity=0.12, line_width=0,
                      annotation_text="Restricciones COVID-19", annotation_position="top left")
    for fecha, texto in [("2022-03-04", "Fin mascarilla"), ("2023-03-31", "Fin emergencia")]:
        if ini <= pd.Timestamp(fecha) <= fin:
            fig.add_vline(x=fecha, line_dash="dot", line_color=ROJO)
            fig.add_annotation(x=fecha, y=1, yref="paper", text=texto, showarrow=False, xanchor="left",
                               font=dict(color=ROJO))
    fig.update_layout(**LAYOUT)
    fig.update_layout(height=430, hovermode="x unified", xaxis_title="", yaxis_title="Delitos por mes",
                      legend=dict(orientation="h", y=-0.25, title=""))
    fig.update_xaxes(tickformat="%m/%Y", rangeslider_visible=True)
    st.plotly_chart(fig, width="stretch")
    por_mes = dff.groupby("Mes").size()
    lectura(f"El mes con menos delitos es {por_mes.idxmin():%m/%Y} ({fmt(por_mes.min())}) y el con más es "
            f"{por_mes.idxmax():%m/%Y} ({fmt(por_mes.max())}). El alza empieza después de la reapertura total "
            "(junio 2021) y llega a su máximo en 2022. Con la barra inferior se puede hacer zoom en un período.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        # ---- Polar 1: reloj del delito ------------------------
        st.subheader("Reloj del delito: ¿a qué hora ocurre?")
        r1, r2 = st.columns([2, 1])
        comparar = r1.selectbox("Comparar", ["Gravedad", "Categoría", "Tipo de día", "Sexo", "Buró"], key="radar_cmp")
        sin12 = r2.checkbox("Ocultar 12:00", value=True, key="radar_12",
                            help="Las 12:00 están infladas: es la hora que se anota cuando no se conoce la real.")
        base = dff[dff[comparar].isin(["Mujer", "Hombre"])] if comparar == "Sexo" else dff
        g = plano(base.groupby([comparar, "Hora"], observed=True).size().reset_index(name="Delitos"))
        g["% del grupo"] = g["Delitos"] / g.groupby(comparar)["Delitos"].transform("sum") * 100
        g["Hora del día"] = g["Hora"].map(lambda h: HORAS[h])
        if sin12:
            g = g[g["Hora"] != 12]
        fig = px.line_polar(
            g, r="% del grupo", theta="Hora del día", color=comparar, line_close=True, markers=True,
            category_orders={"Hora del día": HORAS},
            color_discrete_map={**COLOR_GRAVEDAD, **COLOR_CATEGORIA, **COLOR_SEXO, **COLOR_BURO,
                                "Fin de semana": ROJO, "Lunes a viernes": AZUL},
            hover_name=comparar,
            hover_data={comparar: False, "Hora del día": True, "% del grupo": ":.1f", "Delitos": ":,"},
        )
        fig.update_traces(marker_size=4)
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=520, polar=dict(angularaxis=dict(direction="clockwise", rotation=90),
                                                 radialaxis=dict(ticksuffix="%", angle=90)),
                          legend=dict(orientation="h", y=-0.12, title=""))
        st.plotly_chart(fig, width="stretch")
        lectura("Se lee como un reloj de 24 horas con las 00:00 arriba. Cada línea muestra en porcentaje cómo se "
                "reparten en el día los delitos de un grupo, así que se pueden comparar grupos de distinto tamaño. El "
                "delito sube desde las 15:00 y llega al máximo entre las 17 y las 20 h. Comparando por Tipo de día, "
                "el fin de semana la madrugada (00 a 03 h) concentra el 14,6% de los delitos, frente al 10,9% de lunes a viernes.")
    with c2:
        # ---- Polar 2: radar semanal ---------------------------
        st.subheader("Radar semanal: ¿qué día pesa más cada categoría?")
        cats_radar = st.multiselect("Categorías", CATEGORIAS, key="radar_cats",
                                    default=["Violencia y amenazas", "Fraude e identidad", "Robos y hurtos"])
        # El radar respeta los filtros globales: solo se dibujan categorías que existen en dff.
        # Si ninguna de las elegidas está en la selección, se muestran las que sí hay.
        presentes = [c for c in CATEGORIAS if c in contar(dff["Categoría"]).index]
        elegidas = [c for c in cats_radar if c in presentes] or presentes
        if cats_radar and not any(c in presentes for c in cats_radar):
            st.caption("Ninguna de las categorías elegidas está en los filtros globales: se muestran las que sí hay.")
        g = plano(dff[dff["Categoría"].isin(elegidas)]
                  .groupby(["Categoría", "Día"], observed=True).size().reset_index(name="Delitos"))
        g["Índice (100 = día promedio)"] = g["Delitos"] / g.groupby("Categoría")["Delitos"].transform("mean") * 100
        fig = px.line_polar(
            g, r="Índice (100 = día promedio)", theta="Día", color="Categoría", line_close=True, markers=True,
            category_orders={"Día": DIAS_ES, "Categoría": CATEGORIAS}, color_discrete_map=COLOR_CATEGORIA,
            hover_name="Categoría",
            hover_data={"Categoría": False, "Delitos": ":,", "Índice (100 = día promedio)": ":.0f"},
        )
        fig.update_traces(marker_size=4)
        fig.update_layout(**LAYOUT)
        # eje radial desde 50 para que las líneas no crucen por el centro (más abajo si algún día baja de 50)
        rmin = min(50, g["Índice (100 = día promedio)"].min() - 5)
        fig.update_layout(height=520, polar=dict(angularaxis=dict(direction="clockwise", rotation=90),
                                                 radialaxis=dict(range=[rmin, g["Índice (100 = día promedio)"].max() + 5])),
                          legend=dict(orientation="h", y=-0.12, title=""))
        st.plotly_chart(fig, width="stretch")
        lectura("Un índice de 100 equivale al día promedio de esa categoría. Con todos los datos, la violencia sube el "
                "fin de semana (domingo 112, sábado 108), el fraude baja el sábado (82) y el domingo (74) porque se "
                "detecta en días hábiles, y los robos y hurtos llegan a su máximo el viernes (114).")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Día de la semana × hora")
        tabla_dh = dff.groupby(["Día", "Hora"], observed=True).size().unstack(fill_value=0)
        tabla_dh.index = tabla_dh.index.astype(str)
        tabla_dh = tabla_dh.reindex(index=DIAS_ES, columns=range(24), fill_value=0)
        fig = px.imshow(tabla_dh, color_continuous_scale="Reds", aspect="auto",
                        labels=dict(x="Hora del día", y="", color="Delitos"))
        fig.update_traces(hovertemplate="<b>%{y} a las %{x}:00</b><br>%{z:,} delitos<extra></extra>")
        fig.update_xaxes(dtick=2)
        fig.add_annotation(x=12, y=-0.5, ax=0, ay=-28, text="12:00 inflada", arrowcolor=AZUL, font=dict(color=AZUL))
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=400, margin=dict(t=60, b=40, l=80, r=20))
        st.plotly_chart(fig, width="stretch")
        celdas = tabla_dh.drop(columns=12).stack()
        dia_max, hora_max = celdas.idxmax()
        hora_min = tabla_dh.sum().idxmin()
        lectura(f"Sin contar las 12:00, el momento con más delitos es el {dia_max.lower()} a las {hora_max}:00 "
                f"({fmt(celdas.max())} delitos). La hora con menos delitos es las {hora_min:02d}:00, y la franja de "
                "03:00 a 06:00 es la más baja todos los días.")
    with c2:
        st.subheader("Año × mes: promedio diario")
        g = dff.groupby(["Año", "Mes del año"]).agg(Delitos=("Grave", "size"), Dias=("Fecha", "nunique")).reset_index()
        g["Por día"] = g["Delitos"] / g["Dias"]
        tabla = g.pivot(index="Año", columns="Mes del año", values="Por día").reindex(columns=range(1, 13))
        tabla.columns = MESES
        fig = px.imshow(tabla.round(0), text_auto=".0f", aspect="auto", color_continuous_scale="Reds",
                        labels=dict(x="Mes", y="Año", color="Delitos por día"))
        fig.update_traces(hovertemplate="<b>%{x} %{y}</b><br>%{z:.0f} delitos por día<extra></extra>")
        fig.update_yaxes(type="category")
        fig.update_layout(**LAYOUT)
        fig.update_layout(height=400, margin=dict(t=60, b=40, l=60, r=20))
        st.plotly_chart(fig, width="stretch")
        (a_min, m_min), (a_max, m_max) = g.set_index(["Año", "Mes del año"])["Por día"].idxmin(), \
            g.set_index(["Año", "Mes del año"])["Por día"].idxmax()
        lectura(f"Se usa el promedio diario y no el total para poder comparar meses de distinto largo. El mínimo es "
                f"{MESES[m_min - 1]} {a_min} ({g['Por día'].min():.0f} por día) y el máximo {MESES[m_max - 1]} "
                f"{a_max} ({g['Por día'].max():.0f} por día). Mediados de 2020 y comienzos de 2021 (restricciones) "
                "se ven más claros y 2022 es la fila más oscura. Diciembre de 2023 no está porque los datos están incompletos.")

    st.divider()
    # ---- Mapa animado por año ---------------------------------
    st.subheader("Evolución en el mapa: delitos por día en cada área, año a año")
    g = plano(dff_mapa.groupby(["Año", "Área"], observed=True)
              .agg(Delitos=("Grave", "size"), Dias=("Fecha", "nunique"),
                   lat=("latitude", "mean"), lon=("longitude", "mean")).reset_index())
    g["Delitos por día"] = g["Delitos"] / g.groupby("Año")["Dias"].transform("max")
    g["Buró"] = g["Área"].map(BURO)
    fig = px.scatter_map(
        g, lat="lat", lon="lon", size="Delitos por día", color="Buró", color_discrete_map=COLOR_BURO,
        animation_frame="Año", size_max=40, hover_name="Área",
        hover_data={"lat": False, "lon": False, "Delitos": ":,", "Delitos por día": ":.1f", "Buró": True},
        map_style=ESTILOS_MAPA[estilo], center=centro, zoom=zoom - 0.2,
    )
    fig.update_layout(**LAYOUT)
    fig.update_layout(height=560, margin=dict(t=0, b=0, l=0, r=0), map_layers=BORDES,
                      legend=dict(orientation="h", y=0.99, x=0.01, title="Buró", bgcolor="rgba(255,255,255,.8)"))
    st.plotly_chart(fig, width="stretch")
    lectura("Con el botón de reproducir (abajo a la izquierda) el mapa se anima por año.\n\nDónde se concentra: "
            "Central es la burbuja que más crece entre 2020 y 2022 y pasa del 2.º al 1.er lugar.\n\nDónde no: las "
            "burbujas del Valle cambian poco de un año a otro.\n\nQué implica: el alza después de la pandemia no fue "
            "pareja en la ciudad, se concentró en el centro, así que el refuerzo debería partir por ahí.")

# ── 12. PESTAÑA COMPARAR ÁREAS ───────────────────────────────
with tab_comparar:
    st.subheader("Comparador de áreas: A vs B")
    c1, c2, c3 = st.columns([1, 1, 1.4])
    area_a = c1.selectbox("Área A", AREAS, index=AREAS.index("Central"), key="cmp_a")
    area_b = c2.selectbox("Área B", AREAS, index=AREAS.index("77th Street"), key="cmp_b")
    dim_cmp = c3.radio("Comparar el perfil por", ["Categoría", "Lugar", "Arma"], horizontal=True, key="cmp_dim")

    # Este comparador ignora el filtro de área del sidebar (usa todos los demás filtros globales)
    base = df[mask_sin_area & df["Área"].isin([area_a, area_b])]

    if area_a == area_b:
        st.info("Elige dos áreas distintas.")
    elif base["Área"].nunique() < 2:
        st.info("Con los filtros actuales una de las dos áreas no tiene delitos.")
    else:
        def resumen(a):
            d = base[base["Área"] == a]
            return {"Delitos": len(d), "Por km² al año": len(d) / KM2[a] / max(dias_sel / 365.25, 1 / 365.25),
                    "% graves": d["Grave"].mean() * 100, "% arresto": d["Arresto"].mean() * 100,
                    "% mujeres": (d["Mujer"].mean() * 100) if d["Mujer"].notna().any() else 0,
                    "Edad mediana": d["Edad"].median()}

        ra, rb = resumen(area_a), resumen(area_b)
        st.caption(f"Se muestran los valores de {area_b} y, debajo, la diferencia con {area_a}. "
                   "Este comparador usa todos los filtros globales menos el de área.")
        m = st.columns(6)
        formatos = [("Delitos", fmt, lambda d: f"{'+' if d >= 0 else '-'}{fmt(abs(d))}"),
                    ("Por km² al año", fmt, lambda d: f"{'+' if d >= 0 else '-'}{fmt(abs(d))}"),
                    ("% graves", pct, lambda d: f"{d:+.1f} pp".replace(".", ",")),
                    ("% arresto", pct, lambda d: f"{d:+.1f} pp".replace(".", ",")),
                    ("% mujeres", pct, lambda d: f"{d:+.1f} pp".replace(".", ",")),
                    ("Edad mediana", lambda v: f"{v:.0f} años", lambda d: f"{d:+.0f} año{'s' if abs(round(d)) != 1 else ''}")]
        for i, (k, f_valor, f_delta) in enumerate(formatos):
            m[i].metric(k, f_valor(rb[k]), delta=f"{f_delta(rb[k] - ra[k])} vs {area_a}", delta_color="off",
                        help=f"{area_a}: {f_valor(ra[k])} | {area_b}: {f_valor(rb[k])}")

        col1, col2 = st.columns(2)
        g = plano(base.groupby(["Área", dim_cmp], observed=True).size().reset_index(name="Delitos"))
        g["%"] = g["Delitos"] / g.groupby("Área")["Delitos"].transform("sum") * 100
        orden = g[g["Área"] == area_a].sort_values("%")[dim_cmp].tolist()
        orden += [c for c in g[dim_cmp].unique() if c not in orden]
        with col1:
            # Gráfico de mariposa: A a la izquierda (negativo), B a la derecha
            g["Valor"] = g["%"].where(g["Área"] == area_b, -g["%"])
            fig = px.bar(g, x="Valor", y=dim_cmp, color="Área", orientation="h", barmode="relative",
                         color_discrete_map={area_a: ROJO, area_b: AZUL},
                         category_orders={dim_cmp: orden, "Área": [area_a, area_b]},
                         hover_name="Área", hover_data={"Valor": False, "%": ":.1f", "Delitos": ":,", "Área": False},
                         title=f"Perfil por {dim_cmp.lower()}: % de los delitos de cada área")
            tope = g["%"].max() * 1.1
            ticks = [v for v in range(-100, 101, 10) if abs(v) <= tope]
            fig.update_layout(**LAYOUT)
            fig.update_layout(height=460, xaxis=dict(title=f"{area_a} (izquierda) | {area_b} (derecha), % de los delitos",
                                                     tickvals=ticks, ticktext=[str(abs(v)) for v in ticks],
                                                     range=[-tope, tope]),
                              yaxis_title="", legend=dict(orientation="h", y=-0.2, title=""))
            st.plotly_chart(fig, width="stretch")
        with col2:
            # Radar: perfil de las dos áreas
            fig = px.line_polar(g, r="%", theta=dim_cmp, color="Área", line_close=True, markers=True,
                                color_discrete_map={area_a: ROJO, area_b: AZUL},
                                category_orders={dim_cmp: orden[::-1]},
                                hover_name="Área", hover_data={"Área": False, "%": ":.1f", "Delitos": ":,"},
                                title="Mismo perfil en radar")
            fig.update_traces(fill="toself", opacity=0.6)
            fig.update_layout(**LAYOUT)
            fig.update_layout(height=460, polar=dict(radialaxis=dict(ticksuffix="%")),
                              legend=dict(orientation="h", y=-0.12, title=""))
            st.plotly_chart(fig, width="stretch")
        dif = g.pivot(index=dim_cmp, columns="Área", values="%").fillna(0)
        dif["dif"] = dif[area_b] - dif[area_a]
        lectura(f"La mayor diferencia de perfil está en {dif['dif'].abs().idxmax()}, con "
                f"{pct(dif.loc[dif['dif'].abs().idxmax(), area_a])} en {area_a} frente a "
                f"{pct(dif.loc[dif['dif'].abs().idxmax(), area_b])} en {area_b}. Aunque dos áreas tengan un volumen parecido, "
                "pueden necesitar estrategias distintas.")

    st.divider()
    # ---- Relaciones entre indicadores de las 21 áreas ---------
    st.subheader("Relación entre densidad del delito y tasa de arresto (21 áreas)")
    vista = st.radio("Vista", ["Todo el período", "Animado por año"], horizontal=True,
                     key="rel_vista")
    por = ["Área", "Año"] if vista.startswith("Animado") else ["Área"]
    g = plano(dff.groupby(por, observed=True)
              .agg(Delitos=("Grave", "size"), Arresto=("Arresto", "mean"), Graves=("Grave", "mean"),
                   Dias=("Fecha", "nunique")).reset_index())
    g["Graves"] *= 100
    if vista.startswith("Animado"):
        g["Dias"] = g.groupby("Año")["Dias"].transform("max")
    else:
        g["Dias"] = dias_sel
    g["Arresto"] *= 100
    g["Delitos por km² al año"] = g["Delitos"] / g["Área"].map(KM2) / (g["Dias"] / 365.25)
    g["Buró"] = g["Área"].map(BURO)
    g = g.rename(columns={"Arresto": "% con arresto", "Graves": "% delitos graves"})
    # Nombre fijo solo en el 25% de áreas más densas (las demás se ven al pasar el cursor)
    claves = ["Año"] if vista.startswith("Animado") else []
    q75 = (g.groupby(claves)["Delitos por km² al año"].transform(lambda s: s.quantile(0.75)) if claves
           else g["Delitos por km² al año"].quantile(0.75))
    g["Etiqueta"] = g["Área"].where(g["Delitos por km² al año"] >= q75, "")
    argumentos = dict(x="Delitos por km² al año", y="% con arresto", size="Delitos", color="Buró",
                      color_discrete_map=COLOR_BURO, hover_name="Área", size_max=45, text="Etiqueta",
                      hover_data={"Delitos": ":,", "Delitos por km² al año": ":,.0f", "% con arresto": ":.1f",
                                  "% delitos graves": ":.1f", "Buró": False, "Etiqueta": False})
    if vista.startswith("Animado"):
        fig = px.scatter(g, animation_frame="Año",
                         range_x=[0, g["Delitos por km² al año"].max() * 1.15],
                         range_y=[0, g["% con arresto"].max() * 1.15], **argumentos)
    else:
        fig = px.scatter(g, **argumentos)
    fig.update_traces(textposition="top center", textfont_size=10, selector=dict(mode="markers+text"))
    fig.update_layout(**LAYOUT)
    fig.update_layout(height=560, xaxis_title="Delitos por km² al año",
                      yaxis_title="% de casos con arresto", legend=dict(orientation="h", y=-0.15, title="Buró"))
    st.plotly_chart(fig, width="stretch")
    corr = g[["Delitos por km² al año", "% con arresto"]].corr(method="spearman").iloc[0, 1] if len(g) > 2 else float("nan")
    mas, menos = g.nlargest(1, "% con arresto").iloc[0], g.nsmallest(1, "% con arresto").iloc[0]
    lectura(f"Cada burbuja es un área y su tamaño es la cantidad de delitos. La correlación de Spearman entre densidad "
            f"y arresto es {num(corr, 2)}, es decir, donde el delito es más denso menos casos terminan en arresto. Las "
            "áreas del Valle (celeste), que son las menos densas, arrestan más, y Central, la más densa, está entre las "
            f"que menos. En esta selección el mayor arresto está en {mas['Área']} ({pct(mas['% con arresto'])}) y el "
            f"menor en {menos['Área']} ({pct(menos['% con arresto'])}). Esto muestra una asociación y no prueba una causa "
            "(también puede influir el tipo de delito de cada área).")

    st.divider()
    st.subheader("Tasa de arresto por área y categoría")
    g = plano(dff.groupby(["Área", "Categoría"], observed=True)
              .agg(Arresto=("Arresto", "mean"), Delitos=("Grave", "size")).reset_index())
    g = g[g["Delitos"] >= 30]                       # evitar % con muy pocos casos
    tabla = g.pivot(index="Área", columns="Categoría", values="Arresto").mul(100)
    tabla = tabla.reindex(columns=[c for c in CATEGORIAS if c in tabla.columns])
    tabla = tabla.loc[tabla.mean(axis=1).sort_values(ascending=False).index]
    fig = px.imshow(tabla.round(1), text_auto=".0f", aspect="auto", color_continuous_scale="Blues",
                    labels=dict(x="Categoría", y="Área", color="% con arresto"))
    fig.update_traces(hovertemplate="<b>%{y}</b>, %{x}<br>%{z:.1f}% de los casos con arresto<extra></extra>")
    fig.update_layout(**LAYOUT)
    fig.update_layout(height=max(320, 28 * len(tabla)), xaxis_title="", yaxis_title="")
    st.plotly_chart(fig, width="stretch")
    lectura("Las celdas vacías tienen menos de 30 casos. Vehículos y fraude tienen tasas de arresto muy bajas en todas "
            "las áreas y la violencia es la que más termina en arresto. Al comparar dentro de una misma columna se "
            "compara el mismo tipo de delito, y aun así las áreas del Valle arrestan más que Central.")

# ── 13. PESTAÑA HALLAZGOS ────────────────────────────────────
with tab_hallazgos:
    st.subheader("¿Dónde, cuándo y a quién debe priorizar la prevención la LAPD?")
    st.markdown("""
| # | Hallazgo (datos completos, 2020 a nov-2023) | Dónde verlo | Recomendación |
|---|---|---|---|
| 1. Dónde | El delito se concentra en Central (Downtown) y Hollywood. Central es el área con más delitos desde 2021 y la de mayor densidad por km² de la ciudad, y los puntos calientes abarcan pocas cuadras. | Pestaña Dónde: coropleta por km² y mapa de densidad | Reforzar Central y Hollywood y priorizar según la densidad además de la cantidad. Priorizar también por delito, por ejemplo robo desde vehículo en Central y robo de vehículo en 77th Street. |
| 2. A quién | El perfil de la víctima cambia según el delito (% sobre todas las denuncias de cada delito, como en el Certamen 2). En robo de identidad el 58% son mujeres, en robo desde vehículo el 56% son hombres y en robo a vivienda la mediana de edad es 45 años. Además, en violencia de pareja el 76% son mujeres y en agresión con arma el 71% son hombres. | Pestaña A quién: sexo y edad por delito, categorías paralelas | Campañas de prevención separadas por delito y perfil de víctima. |
| 3. Cuándo | Los delitos subieron un 17,5% entre 2020 y 2022, con la reapertura después de la pandemia. La franja con más delitos va de 15:00 a 20:00 (un tercio del total, con el máximo a las 18:00) y el viernes es el día con más delitos. Las 12:00 aparecen infladas porque es la hora que se anota cuando no se conoce la real. | Pestaña Cuándo: línea mensual y reloj del delito | Concentrar turnos entre 15:00 y 20:00, en especial los viernes. |
| 4. Arrestos | Solo el 9,0% de los casos termina en arresto (vehículos 2,6%, fraude 1,7%). Donde el delito es más denso se arresta menos: por buró, Valle 11,2% frente a Central 7,9%, y por área, desde Harbor (12,7%) hasta Central (6,4%). La correlación de Spearman entre densidad y arresto en las 21 áreas es -0,37. | Pestañas Comparar áreas y Qué | Reforzar la capacidad de investigación en las áreas densas con menos arresto (Central 6,4% y Southeast 6,6%) y estudiar qué hacen distinto las áreas del Valle. |

Límites: los datos llegan hasta noviembre de 2023 (diciembre se cortó porque estaba incompleto). Las 12:00 y el
sexo faltante son problemas de registro. No hay datos de 2019 para comparar, y que dos cosas coincidan en el
tiempo no prueba que una cause la otra. Los límites de áreas y distritos son los oficiales del LAPD (LA Times y
LAPD GIS): el 98,7% de los delitos cae dentro del polígono de su área y el 99,8% tiene su distrito en el mapa.
""")
    with st.expander("Metodología y datos"):
        st.markdown(f"""
- Dataset: Crime Data from 2020 to Present (LAPD), Kaggle `asaniczka/crimes-in-los-angeles-2020-2023`, licencia CC0.
- Limpieza (Certamen 2): fechas a `datetime`, corte de diciembre de 2023, arma vacía como "Sin arma",
  sexo H y "-" como X, vacíos como "Sin dato" y retraso de la denuncia en días. La edad 0 o negativa se excluye
  solo en los gráficos de edad, y las coordenadas (0,0) solo en los mapas. Script: `preparar_datos.py`.
- Dataset completo: {fmt(len(df))} filas en `data/delitos_LA_limpio.csv.gz` (19 MB, bajo el límite de 25 MB).
  No se usa muestra para KPIs, coropletas ni agregados. Solo se muestrean los gráficos que dibujan cada fila
  (mapa de puntos, boxplot y paralelas), con `random_state=42`.
- Categorías: las 138 descripciones del LAPD se agrupan en 7 categorías con reglas de texto (ver código).
- Gravedad: Parte 1 (grave) y Parte 2 (menos grave) de la clasificación del FBI que usa el LAPD.
- GeoJSON: 21 áreas y unos 1.135 distritos de reporte del LAPD (`data/lapd_areas.geojson` y
  `data/lapd_distritos.geojson`), con la superficie de cada área en km².
""")

# ── 14. TABLA DE DATOS (DESPLEGABLE) ─────────────────────────
# Se muestran 1.000 filas: mandar 850 mil al navegador sería muy lento.
st.divider()
with st.expander(f"Ver datos filtrados (primeras 1.000 de {fmt(len(dff))} filas)"):
    columnas = ["date_occurred", "Área", "Distrito", "Categoría", "Delito (detalle)", "crime_description",
                "Gravedad", "Lugar", "Arma", "Edad", "Sexo", "Estado", "Retraso (días)"]
    st.dataframe(
        dff[columnas].head(1000).rename(columns={"date_occurred": "Fecha y hora",
                                                 "crime_description": "Descripción LAPD"}),
        width="stretch",
        hide_index=True,
        column_config={"Fecha y hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")},
    )
