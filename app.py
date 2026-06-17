import streamlit as st
import pandas as pd
import io

# --- Configuración Inicial ---
st.set_page_config(page_title="Consolidador de Kilómetros", layout="wide")

NOMBRE_PESTAÑA = "Programacion"
FILTRO_CONCESIONARIO = ['Blanco y Negro Masivo', 'BYNCPC']
TABLA_ESTILO = 'Table Style Light 9'

COLUMNAS_CRUDAS = [
    'Fecha', 'Día tipo', 'Designación de tarea vehículo', 'Línea', 'Tipo de viaje corto', 
    'Sentido', 'Tipo Kilómetros', 'Número de Vehículo', 'Concesionario de Transporte', 
    'Número de tarea vehículo', 'Desde', 'hasta', 'Duración', 'Punto de inicio', 
    'Punto de término', 'Largo', 'Número de viaje', 'Tipo de vehículo del viaje', 
    'Secuencia de arcos', 'Descripción Novedad', 'Concesionario Programado', 
    'Tipo de vehículo Programado', 'Incumplidos', 'Kilometros Programados-Desvios', 
    'Kilometros Programados Plan', 'Observacion Analista Kilometros'
]

COLUMNAS_SALIDA_RESUMEN = [
    'Origen', 'Fecha', 'Día tipo', 'Concesionario Programado', 
    'Concesionario de Transporte', 'Tipo de vehículo del viaje', 
    'Kilometros Programados Plan', 'Largo Total', 'Largo Observado' 
]

# --- Funciones de Procesamiento ---

@st.cache_data
def procesar_archivos(lista_archivos, tipo_origen):
    """Procesa los archivos cargados en Streamlit."""
    datos_carpeta = []
    datos_observados = [] # Para guardar el detalle extra de Arreglados
    
    if not lista_archivos:
        return datos_carpeta, datos_observados
        
    for archivo in lista_archivos:
        try:
            # Leer excel desde el buffer de memoria subido
            df = pd.read_excel(archivo, sheet_name=NOMBRE_PESTAÑA)
            
            # --- 1. Filtrar Concesionario ---
            df_filtrado = df[df['Concesionario Programado'].isin(FILTRO_CONCESIONARIO)].copy()
            
            if df_filtrado.empty:
                continue

            # --- Extraer detalles de Observados (Solo para Arreglados) ---
            if tipo_origen == "Arreglados":
                try:
                    nombre_col_ah = df.columns[33]
                    # Renombrar temporalmente
                    df_filtrado.rename(columns={nombre_col_ah: 'Observacion Analista Kilometros'}, inplace=True)
                    # Filtrar 'Observado'
                    is_observado = df_filtrado['Observacion Analista Kilometros'].astype(str).str.contains('Observado', case=False, na=False)
                    df_observados_solo = df_filtrado[is_observado].copy()
                    
                    if not df_observados_solo.empty:
                        # Mantener hasta la columna AH (índice 33)
                        cols_mantener = df_observados_solo.columns[:34].tolist()
                        df_det = df_observados_solo[cols_mantener].copy()
                        df_det['Archivo Origen'] = archivo.name
                        datos_observados.append(df_det)
                except IndexError:
                    pass # El archivo no tiene tantas columnas
            
            # --- Preparar para la Consolidación ---
            columnas_base = [col for col in COLUMNAS_CRUDAS if col != 'Observacion Analista Kilometros']
            columnas_a_seleccionar = [col for col in columnas_base if col in df_filtrado.columns]
            
            if 'Observacion Analista Kilometros' not in df_filtrado.columns:
                df_filtrado['Observacion Analista Kilometros'] = ''
            columnas_a_seleccionar.append('Observacion Analista Kilometros')
                
            df_final = df_filtrado[columnas_a_seleccionar].copy()
            df_final['Origen'] = tipo_origen
            
            cols_consolidacion = [
                'Fecha', 'Día tipo', 'Concesionario de Transporte', 'Largo', 
                'Tipo de vehículo del viaje', 'Concesionario Programado', 
                'Observacion Analista Kilometros', 'Origen', 'Kilometros Programados Plan'
            ]
            
            df_consolidacion = df_final[[col for col in cols_consolidacion if col in df_final.columns]].copy()
            datos_carpeta.append(df_consolidacion)
            
        except Exception as e:
            st.error(f"Error procesando el archivo {archivo.name}: {e}")
            
    return datos_carpeta, datos_observados


def consolidar_df(df):
    """Aplica la lógica de agrupación y resumen DIARIO."""
    df['Largo'] = pd.to_numeric(df['Largo'], errors='coerce').fillna(0)
    df['Kilometros Programados Plan'] = pd.to_numeric(df['Kilometros Programados Plan'], errors='coerce').fillna(0)
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.normalize()
    df.dropna(subset=['Fecha'], inplace=True)
    
    group_cols = ['Fecha', 'Día tipo', 'Concesionario Programado', 'Concesionario de Transporte', 'Tipo de vehículo del viaje', 'Origen']
    
    def calculate_observado_largo(group):
        is_observado = group['Observacion Analista Kilometros'].astype(str).str.contains('Observado', case=False, na=False)
        return group.loc[is_observado, 'Largo'].sum()

    df_totales = df.groupby(group_cols).agg(
        Largo_Total=('Largo', 'sum'),
        Kilometros_Plan=('Kilometros Programados Plan', 'sum')
    ).reset_index()

    df_observados = df.groupby(group_cols).apply(calculate_observado_largo).rename('Largo_Observado').reset_index()
    df_consolidado = pd.merge(df_totales, df_observados, on=group_cols, how='left')
    df_consolidado['Largo_Observado'] = df_consolidado['Largo_Observado'].fillna(0)
    
    df_consolidado.rename(columns={
        'Largo_Total': 'Largo Total', 
        'Largo_Observado': 'Largo Observado',
        'Kilometros_Plan': 'Kilometros Programados Plan'
    }, inplace=True)
    
    return df_consolidado[[col for col in COLUMNAS_SALIDA_RESUMEN if col in df_consolidado.columns]].copy()


# --- Interfaz de Streamlit ---
st.title("🚌 Consolidador de Kilómetros en Servicio")
st.markdown("Sube los archivos de **Arreglados** y **Conciliados**. El sistema unificará el resumen, extraerá los detalles y aplicará la lógica que usabas en *Power Query* automáticamente.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Archivos Arreglados")
    archivos_arreglados = st.file_uploader("Selecciona los archivos Excel de Arreglados", accept_multiple_files=True, type=['xlsx', 'xls'], key="arr")

with col2:
    st.subheader("Archivos Conciliados")
    archivos_conciliados = st.file_uploader("Selecciona los archivos Excel de Conciliados", accept_multiple_files=True, type=['xlsx', 'xls'], key="conc")

if st.button("🚀 Procesar Datos", use_container_width=True, type="primary"):
    if not archivos_arreglados and not archivos_conciliados:
        st.warning("Por favor, sube al menos un archivo para comenzar.")
    else:
        with st.spinner("Procesando archivos..."):
            # 1. Leer y extraer la data base
            datos_arr, detalles_obs = procesar_archivos(archivos_arreglados, "Arreglados")
            datos_conc, _ = procesar_archivos(archivos_conciliados, "Conciliados")
            
            todos_los_datos = datos_arr + datos_conc
            
            if not todos_los_datos:
                st.error("No se encontraron datos válidos para procesar en los archivos subidos.")
            else:
                # 2. Consolidar Base
                df_crudo = pd.concat(todos_los_datos, ignore_index=True)
                df_resumen = consolidar_df(df_crudo)
                
                df_arreglados_resumen = df_resumen[df_resumen['Origen'] == 'Arreglados'].drop(columns=['Origen'])
                df_conciliados_resumen = df_resumen[df_resumen['Origen'] == 'Conciliados'].drop(columns=['Origen'])
                
                # --- 3. REPLICA DE POWER QUERY ---
                # Agrupamos la de Conciliados (como el paso de "Sin Duplicados" en M)
                df_conc_agrupado = df_conciliados_resumen.groupby(
                    ['Fecha', 'Día tipo', 'Concesionario Programado', 'Tipo de vehículo del viaje'],
                    as_index=False
                ).agg(Largo_Conciliado=('Largo Total', 'sum'))
                
                # Merge (Unión LeftOuter) con la tabla Arreglados
                df_powerquery_final = pd.merge(
                    df_arreglados_resumen,
                    df_conc_agrupado,
                    on=['Fecha', 'Día tipo', 'Concesionario Programado', 'Tipo de vehículo del viaje'],
                    how='left'
                )
                df_powerquery_final['Largo_Conciliado'] = df_powerquery_final['Largo_Conciliado'].fillna(0)

                # --- 4. Generación de Archivos para Descargar (En Memoria) ---
                
                # Archivo 1: Consolidado y Cruce Final
                buffer_consolidado = io.BytesIO()
                with pd.ExcelWriter(buffer_consolidado, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as writer:
                    df_arreglados_resumen.to_excel(writer, sheet_name='Resumen_Arreglados', index=False)
                    df_conciliados_resumen.to_excel(writer, sheet_name='Resumen_Conciliados', index=False)
                    df_powerquery_final.to_excel(writer, sheet_name='Cruce_Final_PQ', index=False) # Resultado del PowerQuery
                    
                    # Formato de tablas
                    for sheet_name, df_sheet in zip(
                        ['Resumen_Arreglados', 'Resumen_Conciliados', 'Cruce_Final_PQ'], 
                        [df_arreglados_resumen, df_conciliados_resumen, df_powerquery_final]
                    ):
                        if not df_sheet.empty:
                            worksheet = writer.sheets[sheet_name]
                            worksheet.add_table(0, 0, df_sheet.shape[0], df_sheet.shape[1] - 1, {
                                'columns': [{'header': col} for col in df_sheet.columns],
                                'name': f'Tabla_{sheet_name}', 'style': TABLA_ESTILO
                            })

                # Archivo 2: Detalle Observados
                buffer_detalles = io.BytesIO()
                hay_detalles = len(detalles_obs) > 0
                if hay_detalles:
                    df_detalles = pd.concat(detalles_obs, ignore_index=True)
                    with pd.ExcelWriter(buffer_detalles, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as writer:
                        df_detalles.to_excel(writer, sheet_name='Detalle_Observados', index=False)
                        worksheet = writer.sheets['Detalle_Observados']
                        worksheet.add_table(0, 0, df_detalles.shape[0], df_detalles.shape[1] - 1, {
                            'columns': [{'header': str(col)} for col in df_detalles.columns],
                            'name': 'Tabla_Detalle_Observados', 'style': TABLA_ESTILO
                        })

                # --- 5. Interfaz de Descarga ---
                st.success("✅ ¡Proceso completado exitosamente!")
                
                st.subheader("📥 Descargar Resultados")
                st.download_button(
                    label="📄 Descargar Consolidado y Cruce (Ex-PowerQuery)",
                    data=buffer_consolidado.getvalue(),
                    file_name="Consolidado_Kilometros_RESUMEN_App.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
                
                if hay_detalles:
                    st.download_button(
                        label="📄 Descargar Detalles 'Observados'",
                        data=buffer_detalles.getvalue(),
                        file_name="Detalle_Registros_Observados_App.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
