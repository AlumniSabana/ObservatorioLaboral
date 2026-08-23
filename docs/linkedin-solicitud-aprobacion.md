# Solicitud de aprobación — Uso de ofertas públicas de LinkedIn

**Para:** Dirección de Alumni / Asesoría jurídica — Universidad de La Sabana
**De:** Equipo del Observatorio Laboral
**Asunto:** Autorización para incorporar ofertas de empleo públicas de LinkedIn como fuente de datos

---

## Qué se quiere hacer

Incorporar al Observatorio Laboral las **ofertas de empleo publicadas en Colombia** que
LinkedIn muestra públicamente a cualquier visitante (sin iniciar sesión), para
complementar las fuentes actuales (Adzuna, Google Jobs, GEIH-DANE, SPE).

| Parámetro | Definición |
|---|---|
| **Qué se recolecta** | Únicamente ofertas de empleo: cargo, empresa, ciudad, fecha, nivel de experiencia y descripción del puesto. |
| **Qué NO se recolecta** | **Ningún dato de personas**: ni perfiles, ni candidatos, ni reclutadores, ni contactos. |
| **Frecuencia** | **Trimestral** (4 veces al año), una búsqueda por programa académico. |
| **Finalidad** | Académica y de orientación a egresados. **No comercial**; los datos no se revenden ni se comparten con terceros. |
| **Volumen** | Mínimo: máximo 3 páginas por programa, con pausas entre peticiones. |

## Por qué aporta

Es la única fuente disponible que entrega, para el mercado **colombiano**, el
**nivel de experiencia declarado** por el empleador (junior / senior / etc.).
Hoy ese dato se infiere del título de la vacante, con precisión limitada.
Además, cubre ofertas en español que las otras fuentes no alcanzan.

## Situación legal (transparencia completa)

Se distinguen dos capas, y conviene separarlas:

**1. Protección de datos personales — NO aplica.**
Al limitar la recolección a ofertas de empresas (personas jurídicas) y excluir
por completo los perfiles de personas, no se tratan datos personales. Queda
fuera del alcance de la **Ley 1581 de 2012 (habeas data)** y del GDPR.

**2. Términos de Uso de LinkedIn — sí aplica, como asunto contractual.**
Los ToS de LinkedIn prohíben el acceso automatizado a su plataforma, sin
importar el volumen. Precisiones importantes:

- **No constituye delito.** En *hiQ Labs v. LinkedIn*, el Tribunal del Noveno
  Circuito (EE. UU.) determinó que recolectar datos **públicos** no viola la ley
  de fraude informático (CFAA).
- **Sí es un incumplimiento contractual.** LinkedIn ganó ese litigio por esa vía.
  Es, por tanto, un riesgo de naturaleza contractual, no penal.
- **El riesgo práctico a esta escala es mínimo:** una consulta trimestral, no
  comercial y sin datos personales tiene una probabilidad de detección o de
  acción legal muy baja. El precedente citado involucraba recolección masiva con
  fines comerciales.

## Salvaguardas ya implementadas en el código

1. **Desactivado por defecto.** La función está programada pero **inerte**: no
   ejecuta ninguna petición mientras no se autorice (`LINKEDIN_HABILITADO=false`).
   Activarla exige un cambio de configuración deliberado.
2. **Solo ofertas.** No existe código para leer perfiles de personas.
3. **Se detiene si LinkedIn lo pide.** Ante una respuesta de limitación (HTTP 429)
   la recolección se aborta por completo: no reintenta, no rota direcciones IP ni
   usa servidores proxy para evadir controles.
4. **Identificación honesta.** Las peticiones se identifican como el proyecto
   académico de la Universidad, sin suplantar un navegador.
5. **Huella mínima.** Tope bajo de páginas y pausas entre peticiones.

## Decisión solicitada

Se solicita autorización para activar esta fuente **en los términos descritos**
(solo ofertas, trimestral, no comercial). Si la Universidad prefiere no asumir
ninguna exposición contractual, el Observatorio continúa operando con sus fuentes
actuales, todas ellas plenamente autorizadas.

**Aprobado por:** ______________________  **Fecha:** ____________

---

*Nota técnica: una vez aprobado, activar con `LINKEDIN_HABILITADO=true` en
`src/backend/.env` y ejecutar la migración `005_linkedin.sql`. Detalles en
`src/backend/LinkedIn/linkedin_service.py`.*
