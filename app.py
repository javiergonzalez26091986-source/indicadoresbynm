import streamlit as st
import pandas as pd
import io

# --- Configuración Inicial ---
st.set_page_config(page_title="Consolidador Total de Kilómetros", layout="wide")
TABLA_ESTILO = 'Table Style Light 9'

st.title("🚌 Consolidador Total de Kilómetros")
st.markdown("Sube todos los insumos. El sistema unificará Arreglados, Conciliados, Programación, Novedades (Reporte de Operación), Observaciones y Actas en un solo **Consolidado Maestro**.")

# --- Interfaz de Carga de Archivos ---
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1. Kms en Servicio")
    archivos_arreglados = st.file_uploader("📁 Arreglados (Crudos o Resumen)", accept_multiple_files=True, type=['xlsx', 'xls', 'csv'])
    archivos_conciliados = st.file_uploader("📁 Conciliados (Crudos o Resumen)", accept_multiple_files=True, type=['xlsx', 'xls', 'csv'])

with col2:
    st.subheader("2. Operación y Novedades")
    archivos_reporte = st.file_uploader("📄 Reporte de Operación", accept_multiple_files=True, type=['xlsx', 'xls', 'csv'])
    archivo_bd = st.file_uploader("🗄️ Archivo BD (Jerarquías)", accept_multiple_files=False, type=['xlsx', 'xls', 'csv'])
    archivos_observaciones = st.file_uploader("👀 Observaciones", accept_multiple_files=True, type=['xlsx', 'xls', 'csv'])

with col3:
    st.subheader("3. Planeación y Actas")
    archivos_programacion = st.file_uploader("📅 Consolidado Programación", accept_multiple_files=True, type=['xlsx', 'xls', 'csv'])
    archivos_actas = st.file_uploader("📑 Actas", accept_multiple_files=True, type=['xlsx', 'xls', 'csv'])

# Función para leer múltiples archivos
def cargar_multiples_archivos(lista_archivos):
    if not lista_archivos:
        return pd.DataFrame()
    dfs = []
    for archivo in lista_archivos:
        if archivo.name.endswith('.csv'):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

# --- BOTÓN DE PROCESAMIENTO ---
if st.button("🚀 Generar Consolidado Total", use_container_width=True, type="primary"):
    
    if not archivos_arreglados or not archivos_conciliados:
        st.error("⚠️ Faltan archivos obligatorios: Por favor carga al menos 'Arreglados' y 'Conciliados'.")
    else:
        with st.spinner("Procesando y cruzando todas las bases de datos..."):
            try:
                # ------------------------------------------------------------------
                # 1. BASE: ARREGLADOS Y CONCILIADOS
                # ------------------------------------------------------------------
                df_arreglados = cargar_multiples_archivos(archivos_arreglados)
                df_conciliados = cargar_multiples_archivos(archivos_conciliados)
                
                # Llaves maestras de cruce
                llaves_cruce = ['Fecha', 'Día tipo', 'Concesionario Programado', 'Tipo de vehículo del viaje']
                
                df_arreglados['Fecha'] = pd.to_datetime(df_arreglados['Fecha'], errors='coerce').dt.normalize()
                df_conciliados['Fecha'] = pd.to_datetime(df_conciliados['Fecha'], errors='coerce').dt.normalize()
                
                # Agrupar Conciliados
                df_conc_agrupado = df_conciliados.groupby(llaves_cruce, as_index=False).agg(
                    Largo_Conciliado=('Largo Total', 'sum')
                )
                
                # Unir Base
                df_consolidado = pd.merge(df_arreglados, df_conc_agrupado, on=llaves_cruce, how='left')
                df_consolidado['Largo_Conciliado'] = df_consolidado['Largo_Conciliado'].fillna(0)
                df_consolidado['Diferencia'] = df_consolidado['Largo Total'] - df_consolidado['Largo_Conciliado']

                # ------------------------------------------------------------------
                # 2. INCORPORAR PROGRAMACIÓN
                # ------------------------------------------------------------------
                df_prog = cargar_multiples_archivos(archivos_programacion)
                if not df_prog.empty:
                    df_prog['Fecha'] = pd.to_datetime(df_prog['Fecha'], errors='coerce').dt.normalize()
                    # Renombrar columnas para que coincidan con las llaves maestras
                    df_prog.rename(columns={'COT': 'Concesionario Programado', 'Tipología': 'Tipo de vehículo del viaje'}, inplace=True)
                    df_prog_agrupado = df_prog.groupby(['Fecha', 'Concesionario Programado', 'Tipo de vehículo del viaje'], as_index=False).agg(
                        Kilómetros_programados=('Largo', 'sum')
                    )
                    df_consolidado = pd.merge(df_consolidado, df_prog_agrupado, on=['Fecha', 'Concesionario Programado', 'Tipo de vehículo del viaje'], how='left')

                # ------------------------------------------------------------------
                # 3. INCORPORAR OBSERVACIONES (Aceptadas / No Aceptadas)
                # ------------------------------------------------------------------
                df_obs = cargar_multiples_archivos(archivos_observaciones)
                if not df_obs.empty:
                    df_obs['Fecha'] = pd.to_datetime(df_obs['Fecha'], errors='coerce').dt.normalize()
                    # Se asume que existe una columna 'Respuesta UTRYT' (o similar) que dice "Se acepta" o "No se acepta"
                    # Y una columna 'Largo_Observado' (Ajusta los nombres según tu archivo real)
                    if 'Respuesta UTRYT ' in df_obs.columns and 'Largo_Observado' in df_obs.columns:
                        # Filtrar aceptados y sumar
                        df_obs_aceptados = df_obs[df_obs['Respuesta UTRYT '].astype(str).str.contains('Se acepta', case=False, na=False)]
                        obs_ac_agrupado = df_obs_aceptados.groupby(['Fecha', 'Concesionario Programado', 'Tipología'], as_index=False).agg(Largo_aceptado=('Largo_Observado', 'sum'))
                        obs_ac_agrupado.rename(columns={'Tipología': 'Tipo de vehículo del viaje'}, inplace=True)
                        
                        # Filtrar no aceptados y sumar
                        df_obs_rechazados = df_obs[df_obs['Respuesta UTRYT '].astype(str).str.contains('No se acepta', case=False, na=False)]
                        obs_rech_agrupado = df_obs_rechazados.groupby(['Fecha', 'Concesionario Programado', 'Tipología'], as_index=False).agg(Largo_no_aceptado=('Largo_Observado', 'sum'))
                        obs_rech_agrupado.rename(columns={'Tipología': 'Tipo de vehículo del viaje'}, inplace=True)

                        # Cruzar a la tabla principal
                        df_consolidado = pd.merge(df_consolidado, obs_ac_agrupado, on=['Fecha', 'Concesionario Programado', 'Tipo de vehículo del viaje'], how='left')
                        df_consolidado = pd.merge(df_consolidado, obs_rech_agrupado, on=['Fecha', 'Concesionario Programado', 'Tipo de vehículo del viaje'], how='left')

                # ------------------------------------------------------------------
                # 4. INCORPORAR ACTAS (Kms Conciliados Finales)
                # ------------------------------------------------------------------
                df_actas = cargar_multiples_archivos(archivos_actas)
                if not df_actas.empty:
                    df_actas['Fecha'] = pd.to_datetime(df_actas['Fecha'], errors='coerce').dt.normalize()
                    df_actas.rename(columns={'Concesionario': 'Concesionario Programado', 'Tipologia': 'Tipo de vehículo del viaje'}, inplace=True)
                    # Sumar los Kms Ejecutados/Conciliados de las actas
                    actas_agrupado = df_actas.groupby(['Fecha', 'Concesionario Programado', 'Tipo de vehículo del viaje'], as_index=False).agg(
                        Kms_conciliados=('Ejecutados', 'sum') # Asegúrate que la columna se llame 'Ejecutados' en tu Excel
                    )
                    df_consolidado = pd.merge(df_consolidado, actas_agrupado, on=['Fecha', 'Concesionario Programado', 'Tipo de vehículo del viaje'], how='left')

                # ------------------------------------------------------------------
                # 5. REPORTE DE OPERACIÓN Y BD (Incumplimientos y Salidas pivotados)
                # ------------------------------------------------------------------
                df_reporte = cargar_multiples_archivos(archivos_reporte)
                if not df_reporte.empty and archivo_bd is not None:
                    df_bd = pd.read_csv(archivo_bd) if archivo_bd.name.endswith('.csv') else pd.read_excel(archivo_bd)
                    df_reporte['Fecha'] = pd.to_datetime(df_reporte['Fecha'], errors='coerce').dt.normalize()
                    
                    # Cruzar Reporte con BD para traer 'Jerarquía simple'
                    df_reporte = pd.merge(df_reporte, df_bd[['Jerarquía completa', 'Jerarquía simple']], left_on='Novedad', right_on='Jerarquía completa', how='left')
                    
                    # Pivotear los Kms perdidos
                    df_reporte_pivot = df_reporte.pivot_table(
                        index=['Fecha', 'COT', 'Tipo de vehículo del viaje'],
                        columns='Jerarquía simple',
                        values='KMS perdidos',
                        aggfunc='sum',
                        fill_value=0
                    ).reset_index()
                    
                    df_reporte_pivot.rename(columns={'COT': 'Concesionario Programado'}, inplace=True)
                    df_consolidado = pd.merge(df_consolidado, df_reporte_pivot, on=['Fecha', 'Concesionario Programado', 'Tipo de vehículo del viaje'], how='left')

                # ------------------------------------------------------------------
                # 6. CÁLCULOS FINALES Y LIMPIEZA
                # ------------------------------------------------------------------
                # Mes y Quincena
                meses = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                         7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
                df_consolidado['Mes'] = df_consolidado['Fecha'].dt.month.map(meses)
                df_consolidado['Quincena'] = df_consolidado['Fecha'].dt.day.apply(lambda x: '1Q' if x <= 15 else '2Q')

                # Rellenar todos los nulos (archivos que no cruzaron) con 0
                df_consolidado.fillna(0, inplace=True)

                # ------------------------------------------------------------------
                # 7. EXPORTAR A EXCEL
                # ------------------------------------------------------------------
                buffer_consolidado = io.BytesIO()
                with pd.ExcelWriter(buffer_consolidado, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as writer:
                    df_consolidado.to_excel(writer, sheet_name='Consolidado', index=False)
                    
                    # Formato Tabla
                    worksheet = writer.sheets['Consolidado']
                    max_row, max_col = df_consolidado.shape
                    worksheet.add_table(0, 0, max_row, max_col - 1, {
                        'columns': [{'header': str(col)} for col in df_consolidado.columns],
                        'name': 'Tabla_Consolidado_Final', 
                        'style': TABLA_ESTILO
                    })

                st.success("✅ ¡Consolidado Total generado exitosamente! Todos los archivos fueron cruzados.")
                
                # --- BOTÓN DE DESCARGA ---
                st.download_button(
                    label="📥 Descargar Archivo Consolidado Completo",
                    data=buffer_consolidado.getvalue(),
                    file_name="Reporte_Consolidado_Maestro.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
                
                # Vista previa
                st.subheader("Vista Previa del Consolidado")
                st.dataframe(df_consolidado.head(10))

            except KeyError as e:
                st.error(f"⚠️ Error de Columna: No se encontró la columna {str(e)} en alguno de los archivos.")
                st.info("Asegúrate de que los encabezados de tus archivos Excel coincidan exactamente con los nombres que espera el código (ej. 'Concesionario Programado', 'COT', 'Tipología').")
            except Exception as e:
                st.error(f"⚠️ Ocurrió un error inesperado al procesar las bases: {str(e)}")
