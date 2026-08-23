# Anexos del SPE (Servicio Público de Empleo — Colombia)

Datos fuente de la página de competencias colombianas. Se versionan aquí para que
el ETL sea reproducible y quede constancia de con qué periodo se cargó la base.

## Archivos

| Archivo | Contenido |
|---|---|
| `Anexo_ocupaciones_competencias_2023_ene-sep.xlsx` | Ofertas por ocupación (CIUO), municipio y mes + las competencias que piden. 11 hojas. |
| `Anexo_tendencias_2023_ene-sep.xlsx` | Serie mensual 2022–2023 de ocupaciones y competencias. *(aún no cargado)* |

## Periodo

**Enero–septiembre 2023.** Es el periodo de estos anexos, no la fecha de descarga.
Los anexos del SPE son públicos y se publican mensualmente: conviene reemplazarlos
por una versión reciente cada 3–6 meses (misma cadencia que la GEIH).

Descarga: <https://www.serviciodeempleo.gov.co/dataempleo-spe/demanda-laboral>

## Cómo cargarlos

```bash
# desde src/backend/
python -m SPE.cargar_anexos "SPE/data/Anexo_ocupaciones_competencias_2023_ene-sep.xlsx" --anio 2023
```

El ETL hace *upsert*, así que volver a ejecutarlo actualiza en vez de duplicar.
Requiere la migración `007_spe_competencias.sql`.

## Por qué esta fuente

El ranking de skills del Observatorio se derivaba de O*NET (normativo,
Estados Unidos) cruzado con la demanda de cada programa. Estos anexos traen
competencias **observadas** en vacantes colombianas reales, en español, sobre
~1,8 millones de ofertas.

Además, su **CIUO de 2 dígitos es la misma taxonomía que el CNO** que ya usa
`Salarios/salarios_service.PROGRAMA_CNO`, así que cada programa académico se
conecta con sus competencias sin necesidad de ningún mapeo adicional.
