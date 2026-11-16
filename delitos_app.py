# delitos_app.py
# ============================================================
#  DASHBOARD — Radiografía del delito en Los Ángeles (2020–2023)
#  Taller de Visualización de la Información (UDD)
#  Juan Pablo Castillo · Martín Cáceres · Emilio Pacheco
#
#  Ejecutar:  streamlit run delitos_app.py
#  (el archivo Crime_Data_from_2020_to_Present.csv debe estar en
#   la misma carpeta desde donde se ejecuta el comando)
#
#  Problema de negocio: la Policía de Los Ángeles (LAPD) tiene
#  recursos de prevención limitados. El dashboard le permite ver
#  DÓNDE, A QUIÉN y CUÁNDO priorizar (los 3 hallazgos del
#  Certamen 2), filtrando por años, áreas y tipo de delito.
#
#  Idea clave de Streamlit: el script se ejecuta de ARRIBA A ABAJO
#  cada vez que el usuario mueve un widget. Todo el dashboard es
#  código Python normal, leído en orden.
# ============================================================

import pandas as pd
import plotly.express as px
import streamlit as st

# ── 1. CONFIGURACIÓN DE LA PÁGINA ────────────────────────────
# Debe ser la PRIMERA instrucción de Streamlit del script.
st.set_page_config(
    page_title="Delitos en Los Ángeles",
    page_icon="🚓",
    layout="wide",
)

# ── 2. PALETA DE COLORES Y ESTILO COMPARTIDO ─────────────────
# Los mismos colores de los avances y del Certamen 2: así una
# categoría (ej. "Mujer") tiene siempre el mismo color.
AZUL, ROJO, GRIS, SALMON = "#0b2545", "#8B1E1E", "#6c7480", "#e07a6f"
COLOR_SEXO = {"Mujer": ROJO, "Hombre": AZUL, "Desconocido (X)": "#a9b0b9", "Sin dato": "#dde1e6"}
DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Estilo de Plotly reutilizable: se "desempaqueta" con ** en cada
# fig.update_layout(**LAYOUT, ...). separators=",." muestra los
# números en formato chileno (1.234,5).
LAYOUT = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(family="Arial", size=12),
    separators=",.",
    margin=dict(t=40, b=40, l=50, r=20),
)

# Mapa base de calles (Esri): OpenStreetMap y Carto bloquean Colab
CALLES = [{"below": "traces",
           "sourcetype": "raster",
           "sourceattribution": "Esri",
           "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"]}]

# Nombres en español de los 10 delitos más frecuentes
TRADUCCION = {
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
# El robo de vehículo casi nunca tiene una persona como víctima (edad 0)
DELITOS_PERSONA = [d for d in TRADUCCION.values() if d != "Robo de vehículo"]


def fmt(n):
    """Número con punto de miles: 1234567 -> '1.234.567'."""
    return f"{int(round(n)):,}".replace(",", ".")


def pct(x):
    """Porcentaje con coma decimal: 6.789 -> '6,8%'."""
    return f"{x:.1f}%".replace(".", ",")


# ── 3. CARGAR Y PREPARAR LOS DATOS ───────────────────────────
# @st.cache_data: la función se ejecuta UNA SOLA VEZ y Streamlit
# guarda el resultado. Con 850 mil filas es clave: sin caché, cada
# clic en un filtro volvería a leer el CSV de 250 MB.
@st.cache_data(show_spinner="Cargando 850 mil delitos (solo la primera vez)...")
def cargar_datos():
    # Solo las columnas que usa el dashboard (menos memoria)
    df = pd.read_csv("Crime_Data_from_2020_to_Present.csv",
                     usecols=["date_occurred", "area_name", "crime_description",
                              "victim_age", "victim_sex", "latitude", "longitude"])

    # Fechas y corte: diciembre de 2023 solo tiene 4 días de datos
    df["date_occurred"] = pd.to_datetime(df["date_occurred"])
    df = df[df["date_occurred"] < "2023-12-01"].copy()

    # Variables de tiempo
    df["Año"] = df["date_occurred"].dt.year
    df["Mes"] = df["date_occurred"].dt.to_period("M").dt.to_timestamp()
    df["Hora"] = df["date_occurred"].dt.hour
    df["Día"] = df["date_occurred"].dt.day_name().map(dict(zip(DIAS_EN, DIAS_ES)))

    # Misma limpieza del Certamen 2: H y "-" -> X; vacío -> Sin dato
    df["Sexo"] = (df["victim_sex"].replace({"H": "X", "-": "X"}).fillna("Sin dato")
                  .replace({"F": "Mujer", "M": "Hombre", "X": "Desconocido (X)"}))

    # Delito en español (fuera del top 10 -> "Otros delitos")
    df["Delito"] = df["crime_description"].map(TRADUCCION).fillna("Otros delitos")
    df["Área"] = df["area_name"]
    return df


df = cargar_datos()

# ── 4. SIDEBAR — FILTROS GLOBALES ────────────────────────────
# Cada widget DEVUELVE lo que eligió el usuario y lo guardamos en
# una variable normal. Estos filtros afectan TODO el dashboard.
with st.sidebar:
    st.title("🚓 Delitos en LA")
    st.caption("Filtros globales — afectan todos los gráficos")

    # slider de rango -> devuelve una tupla (desde, hasta)
    anio_min, anio_max = st.slider(
        "Años",
        min_value=int(df["Año"].min()),
        max_value=int(df["Año"].max()),
        value=(int(df["Año"].min()), int(df["Año"].max())),
    )

    # multiselect -> lista de opciones elegidas (vacía = todas)
    areas = st.multiselect(
        "Área policial",
        options=sorted(df["Área"].unique()),
        placeholder="Todas las áreas",
    )

    delitos = st.multiselect(
        "Tipo de delito",
        options=list(TRADUCCION.values()) + ["Otros delitos"],
        placeholder="Todos los delitos",
    )

    st.divider()
    st.caption(f"Dataset completo: {fmt(len(df))} delitos (ene-2020 a nov-2023). "
               "Fuente: LAPD vía Kaggle (asaniczka), licencia CC0.")

# ── 5. APLICAR LOS FILTROS (pandas puro) ─────────────────────
# Máscara booleana: True en las filas que cumplen los filtros.
# Si una lista está vacía no se filtra por esa variable.
mask = df["Año"].between(anio_min, anio_max)
if areas:
    mask &= df["Área"].isin(areas)
if delitos:
    mask &= df["Delito"].isin(delitos)

dff = df[mask]  # dff = "dataframe filtrado"

# ── 6. ENCABEZADO ─────────────────────────────────────────────
st.title("Radiografía del delito en Los Ángeles (2020–2023)")
st.markdown("**¿Dónde, a quién y cuándo debe priorizar la prevención la Policía de Los Ángeles?**")
st.caption(f"Mostrando {fmt(len(dff))} de {fmt(len(df))} delitos con los filtros aplicados")

# Si los filtros dejan el DataFrame vacío, avisamos y paramos.
if dff.empty:
    st.warning("No hay delitos para los filtros seleccionados. Ajusta el panel lateral.")
    st.stop()

# ── 7. KPIs (TARJETAS DE MÉTRICAS) ───────────────────────────
k1, k2, k3, k4 = st.columns(4)

dias_periodo = dff["date_occurred"].dt.normalize().nunique()  # días con datos en la selección
por_area = dff["Área"].value_counts()
por_hora = dff[dff["Hora"] != 12]["Hora"].value_counts()      # sin las 12:00 (hora por defecto)
pct_mujer = (dff["Sexo"] == "Mujer").sum() / dff["Sexo"].isin(["Mujer", "Hombre"]).sum() * 100

k1.metric("Delitos", fmt(len(dff)),
          help=f"Promedio de {fmt(len(dff) / dias_periodo)} delitos por día")
k2.metric("Área con más delitos", por_area.index[0],
          help=f"{pct(por_area.iloc[0] / len(dff) * 100)} de los delitos seleccionados")
k3.metric("Hora más crítica", f"{por_hora.index[0]}:00",
          help="Se excluyen las 12:00, hora que se registra por defecto cuando no se conoce la real")
k4.metric("Víctimas mujeres", pct(pct_mujer),
          help="% de mujeres entre las víctimas con sexo conocido (mujer u hombre)")

st.divider()

# ── 8. FILA 1 — DÓNDE: MAPA + RANKING ────────────────────────
st.header("1 · Dónde ocurre")
col1, col2 = st.columns([3, 2])

with col1:
    # Control LOCAL: solo afecta a este mapa (no está en el sidebar)
    tipo_mapa = st.radio("Tipo de mapa", ["Burbujas por área", "Puntos calientes"],
                         horizontal=True, key="tipo_mapa")

    # (0,0) = ubicación faltante según el LAPD -> fuera de los mapas
    dff_mapa = dff[(dff["latitude"] != 0) & (dff["longitude"] != 0)]

    if tipo_mapa == "Burbujas por área":
        # Una burbuja por área: tamaño y color = cantidad de delitos
        g = dff_mapa.groupby("Área").agg(lat=("latitude", "mean"), lon=("longitude", "mean"),
                                         Delitos=("Área", "size")).reset_index()
        fig = px.scatter_map(g, lat="lat", lon="lon", size="Delitos", color="Delitos",
                             hover_name="Área", hover_data={"lat": False, "lon": False},
                             color_continuous_scale="Reds", size_max=32)
    else:
        # Delitos por celda de ~1 km (coordenadas con 2 decimales)
        g = (dff_mapa.groupby([dff_mapa["latitude"].round(2), dff_mapa["longitude"].round(2)])
                     .size().reset_index(name="Delitos"))
        fig = px.density_map(g, lat="latitude", lon="longitude", z="Delitos",
                             radius=25 if areas else 10,   # más grande si el mapa está acercado
                             color_continuous_scale="YlOrRd",
                             range_color=[0, g["Delitos"].quantile(0.99)])  # si no, 2 celdas de Downtown lo dejan pálido

    # Si se eligieron áreas, el mapa se acerca a ellas
    centro = {"lat": dff_mapa["latitude"].mean(), "lon": dff_mapa["longitude"].mean()} if areas \
        else {"lat": 34.05, "lon": -118.35}
    fig.update_layout(**LAYOUT)
    fig.update_layout(map_style="white-bg", map_layers=CALLES, map_center=centro,
                      map_zoom=10.5 if areas else 9, height=520, margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Con 4 o más áreas se comparan áreas; con menos, se comparan los delitos dentro de ellas
    columna = "Área" if dff["Área"].nunique() >= 4 else "Delito"
    st.subheader(f"% de los delitos por {columna.lower()}")
    g = (dff[columna].value_counts(normalize=True) * 100).drop("Otros delitos", errors="ignore")
    g = g.sort_values().reset_index()
    g.columns = [columna, "Porcentaje"]
    g["Etiqueta"] = g["Porcentaje"].map(pct)
    g["Destacado"] = (g["Porcentaje"] == g["Porcentaje"].max()).map({True: "Máximo", False: "Resto"})

    fig = px.bar(g, x="Porcentaje", y=columna, orientation="h", text="Etiqueta",
                 color="Destacado", color_discrete_map={"Máximo": ROJO, "Resto": GRIS})
    fig.update_traces(textposition="outside", offsetgroup="1")   # barras centradas en su fila
    fig.update_layout(**LAYOUT, height=560, showlegend=False, yaxis_title="",
                      xaxis=dict(title="% de los delitos", range=[0, g["Porcentaje"].max() * 1.25]))
    st.plotly_chart(fig, use_container_width=True)

if len(por_area) >= 5:
    resumen = (f"{por_area.index[0]} concentra el {pct(por_area.iloc[0] / len(dff) * 100)} de los delitos "
               f"seleccionados y las 5 primeras áreas suman el {pct(por_area.head(5).sum() / len(dff) * 100)}.")
else:
    principal = dff[dff["Delito"] != "Otros delitos"]["Delito"].value_counts()
    resumen = (f"En las áreas elegidas, el delito más frecuente del top 10 es {principal.index[0]} "
               f"({pct(principal.iloc[0] / len(dff) * 100)} de la selección).") if len(principal) else ""
st.info(f"**Lectura.** {resumen} "
        "El ranking de áreas cambia según el delito: prueba filtrar *Robo desde vehículo* (Central lidera con 15,3%) "
        "o *Robo de vehículo* (77th Street, 7,7%).")

# ── 9. FILA 2 — A QUIÉN: SEXO + EDAD DE LA VÍCTIMA ───────────
st.header("2 · A quién afecta")
dff_persona = dff[dff["Delito"].isin(DELITOS_PERSONA)]

if dff_persona.empty:
    st.info("La selección no incluye delitos con víctima persona (el robo de vehículo casi nunca la tiene).")
else:
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Sexo de la víctima por delito")
        # crosstab con normalize="index" -> % dentro de cada delito (cada fila suma 100)
        tabla = pd.crosstab(dff_persona["Delito"], dff_persona["Sexo"], normalize="index") * 100
        tabla = tabla.reindex(columns=list(COLOR_SEXO), fill_value=0).sort_values("Mujer")
        g = tabla.reset_index().melt(id_vars="Delito", var_name="Sexo", value_name="Porcentaje")
        g["Etiqueta"] = g["Porcentaje"].round(0).astype(int).astype(str).where(g["Porcentaje"] >= 3, "")

        fig = px.bar(g, x="Porcentaje", y="Delito", color="Sexo", orientation="h",
                     text="Etiqueta", barmode="stack",
                     color_discrete_map=COLOR_SEXO,
                     category_orders={"Delito": list(tabla.index), "Sexo": list(COLOR_SEXO)},
                     labels={"Porcentaje": "% de las víctimas", "Delito": ""})
        fig.update_traces(offsetgroup="1")   # mismo grupo para que las barras se apilen al 100%
        fig.update_layout(**LAYOUT, height=480, legend=dict(orientation="h", y=-0.2, title=""))
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Edad de la víctima por delito")
        edad = dff_persona[dff_persona["victim_age"] > 0]       # solo víctimas persona
        orden = edad.groupby("Delito")["victim_age"].median().sort_values()
        # Muestra de 60.000 para que el navegador no se ponga lento (random_state = reproducible)
        muestra = edad.sample(min(len(edad), 60000), random_state=42)

        fig = px.box(muestra, x="victim_age", y="Delito", points="outliers",
                     color_discrete_sequence=[AZUL],
                     category_orders={"Delito": list(orden.index)},
                     labels={"victim_age": "Edad de la víctima (años)", "Delito": ""})
        fig.update_traces(marker_size=3)
        fig.update_layout(**LAYOUT, height=480)
        st.plotly_chart(fig, use_container_width=True)

    mas_mujer, mas_hombre = tabla["Mujer"].idxmax(), tabla["Hombre"].idxmax()
    st.info(f"**Lectura.** Más víctimas mujeres: **{mas_mujer}** ({tabla.loc[mas_mujer, 'Mujer']:.0f}%). "
            f"Más víctimas hombres: **{mas_hombre}** ({tabla.loc[mas_hombre, 'Hombre']:.0f}%). "
            f"La mediana de edad va de {orden.iloc[0]:.0f} años ({orden.index[0]}) a {orden.iloc[-1]:.0f} "
            f"({orden.index[-1]}). Cada delito necesita su propia campaña de prevención.")

# ── 10. FILA 3 — CUÁNDO: LÍNEA MENSUAL CON SELECTBOX LOCAL ───
st.header("3 · Cuándo ocurre")
st.subheader("Delitos por mes y contexto de la pandemia")

# Control LOCAL: elige cómo separar la línea (solo afecta este gráfico)
separar = st.selectbox("Separar la línea por", ["Total", "Tipo de delito (top 5)", "Área (top 5)"],
                       key="sel_linea")

if separar == "Total":
    g = dff.groupby("Mes").size().reset_index(name="Delitos")
    fig = px.line(g, x="Mes", y="Delitos", markers=True, color_discrete_sequence=[AZUL])
else:
    col = "Delito" if separar.startswith("Tipo") else "Área"
    top = dff[col].value_counts().drop("Otros delitos", errors="ignore").head(5).index
    g = dff[dff[col].isin(top)].groupby(["Mes", col]).size().reset_index(name="Delitos")
    fig = px.line(g, x="Mes", y="Delitos", color=col, category_orders={col: list(top)},
                  color_discrete_sequence=[AZUL, ROJO, SALMON, GRIS, "#c9a227"])

# Hitos de la pandemia (solo si caen dentro de los años elegidos)
if anio_min <= 2021:
    fig.add_vrect(x0=max(pd.Timestamp("2020-03-19"), pd.Timestamp(anio_min, 1, 1)),
                  x1=min(pd.Timestamp("2021-06-15"), pd.Timestamp(anio_max, 12, 31)),
                  fillcolor=GRIS, opacity=0.15, line_width=0,
                  annotation_text="Restricciones COVID-19", annotation_position="top left")
for fecha, texto in [("2022-03-04", "Fin mascarilla"), ("2023-03-31", "Fin emergencia")]:
    if anio_min <= int(fecha[:4]) <= anio_max:
        fig.add_vline(x=fecha, line_dash="dot", line_color=ROJO)
        fig.add_annotation(x=fecha, y=1, yref="paper", text=texto, showarrow=False,
                           xanchor="left", font=dict(color=ROJO))
fig.update_layout(**LAYOUT, height=440, hovermode="x unified", xaxis_title="",
                  legend=dict(orientation="h", y=-0.15, title=""))
fig.update_xaxes(tickformat="%m/%Y")
st.plotly_chart(fig, use_container_width=True)

# ── 11. FILA 4 — CUÁNDO: MAPA DE CALOR DÍA x HORA ────────────
st.subheader("Delitos por día de la semana y hora")
tabla_dh = pd.crosstab(dff["Día"], dff["Hora"]).reindex(index=DIAS_ES, columns=range(24), fill_value=0)

fig = px.imshow(tabla_dh, color_continuous_scale="Reds", aspect="auto",
                labels={"x": "Hora del día", "y": "", "color": "Delitos"})
fig.update_xaxes(dtick=1)
fig.add_annotation(x=12, y=-0.5, ax=0, ay=-30, text="12:00 inflada: hora por defecto",
                   arrowcolor=AZUL, font=dict(color=AZUL))
fig.update_layout(**LAYOUT, height=380)
fig.update_layout(margin=dict(t=60, b=40, l=80, r=20))
st.plotly_chart(fig, use_container_width=True)

por_mes = dff.groupby("Mes").size()
celdas = tabla_dh.drop(columns=12).stack()        # sin la columna de las 12:00
dia_max, hora_max = celdas.idxmax()
st.info(f"**Lectura.** Mes con menos delitos: {por_mes.idxmin():%m/%Y} ({fmt(por_mes.min())}); "
        f"con más: {por_mes.idxmax():%m/%Y} ({fmt(por_mes.max())}). El alza empieza tras la reapertura "
        f"de junio de 2021. Sin contar las 12:00, el momento más crítico es el **{dia_max.lower()} a las "
        f"{hora_max}:00** ({fmt(celdas.max())} delitos).")

# ── 12. CONCLUSIONES (DESPLEGABLE) ───────────────────────────
with st.expander("Conclusiones y recomendaciones para la policía", expanded=True):
    st.markdown("""
| Hallazgo | Qué muestra el dashboard | Recomendación |
|---|---|---|
| **1. Dónde** | Central pasó del 2.º lugar en 2020 al 1.º desde 2021 (+53% de 2020 a 2022); los puntos calientes son pocas cuadras de Downtown y Hollywood | Reforzar Central y Hollywood; un mapa de prioridades por delito (robo desde vehículo → Central; robo de vehículo → 77th Street) |
| **2. A quién** | Violencia de pareja: 76% mujeres; robo de identidad: 58% mujeres; agresión con arma: 71% hombres; robo a vivienda: mediana de 45 años | Campañas segmentadas por delito |
| **3. Cuándo** | Alza 2020 → 2022 con la reapertura; peak real el viernes a las 17:00 | Concentrar turnos entre 15:00 y 20:00, en especial los viernes |

**Límites:** datos hasta el 4-dic-2023 (se cortó diciembre); las 12:00 y el sexo faltante son problemas de registro;
no hay 2019 para comparar, y una coincidencia en el tiempo no prueba causa.
""")

# ── 13. TABLA DE DATOS (DESPLEGABLE) ─────────────────────────
# Se muestran las primeras 1.000 filas: mandar 850 mil al navegador sería muy lento.
with st.expander("Ver datos filtrados (primeras 1.000 filas)"):
    columnas = ["date_occurred", "Área", "Delito", "crime_description", "victim_age", "Sexo"]
    st.dataframe(
        dff[columnas].head(1000).rename(columns={"date_occurred": "Fecha y hora",
                                                 "crime_description": "Descripción LAPD",
                                                 "victim_age": "Edad"}),
        use_container_width=True,
        hide_index=True,
    )
