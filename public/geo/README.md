# Geometría de departamentos de Colombia

`colombia-departamentos.json` — los 32 departamentos + Bogotá D.C. en GeoJSON,
para el mapa de la sección "Vacantes por departamento" de Tendencias.

## Origen

Derivado del GeoJSON público de departamentos de Colombia publicado por John
Guerra (gist `43c7656821069d00dcbc`), que a su vez proviene de la cartografía
oficial del DANE. Se descargó el 2026-09-14.

## Qué se le hizo

El original pesa 1,5 MB, demasiado para servirlo en cada carga. Se procesó así:

1. Coordenadas redondeadas a 3 decimales (~110 m, imperceptible a escala país).
2. Simplificación Douglas-Peucker con tolerancia 0,005°.
3. Se eliminaron los puntos duplicados consecutivos que deja el redondeo.
4. Se descartaron las propiedades que el mapa no usa (`AREA`, `PERIMETER`,
   `HECTARES`), dejando solo `codigo` y `nombre`.
5. Los nombres se pasaron a su forma oficial en español con tildes
   (`SANTAFE DE BOGOTA D.C` → `Bogotá D.C.`).

Resultado: 111 KB, 6.909 puntos, los 33 departamentos completos.

## Llave de unión

La propiedad `codigo` es el código DANE (DIVIPOLA) de dos dígitos y es la llave
que cruza con el backend (`Tendencias/geografia.py`, diccionario
`DEPARTAMENTOS`). **No cruzar por nombre**: las fuentes de vacantes escriben los
departamentos de formas distintas y con/sin tildes.

## Cómo regenerarlo

No hay script en el repo porque es un archivo estático que no cambia: la
división político-administrativa de Colombia no se actualiza con el proyecto.
Si hiciera falta, el procedimiento son los 5 pasos de arriba sobre el GeoJSON
original.
