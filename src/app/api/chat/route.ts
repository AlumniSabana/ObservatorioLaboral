/**
 * Ruta API del asistente de IA.
 *
 * Dos modelos distintos según quién pregunta:
 *   - modo='empresas' (página /asistente, chat de Empresas y cultura) -> Gemini,
 *     vía la API REST de Google (streamGenerateContent). Cambio pedido por el
 *     usuario el 12 ago 2026; antes usaba Claude, igual que la burbuja.
 *   - cualquier otro modo (burbuja contextual, floating-chat.tsx en el resto de
 *     páginas) -> se queda en Claude/Anthropic, sin cambios. No se pidió tocarla.
 *
 * Recibe del frontend la pregunta del usuario más el contexto de la página
 * actual (pageTitle + pageContent), arma un "system prompt" que obliga al
 * modelo a responder SOLO con base en ese contexto (o, en 'empresas', a avisar
 * cuando sale de él), y devuelve la respuesta en texto plano por streaming —
 * mismo contrato de salida para ambos modelos, así el frontend no cambia.
 *
 * USO Y COSTO (sep-2026). Al terminar el stream se añade un "tráiler de uso":
 * un carácter NUL + `uso:` + JSON con los tokens que reportó el modelo
 * (Gemini: `usageMetadata` de los chunks SSE; Claude: `usage` del mensaje
 * final) y el costo ESTIMADO con precios configurables por variable de
 * entorno. Los dos clientes lo separan con `separarUso` (src/lib/chat-sesion.ts).
 * Además, cada pregunta se registra en el backend (`POST /asistente/preguntas`)
 * con su categoría (derivada del título de la página), tokens, costo y un id de
 * sesión aleatorio del navegador — nunca IP ni correo. Si el backend o la
 * migración 011 no están, el chat sigue funcionando igual.
 *
 * Las API keys se leen de variables de entorno (nunca se exponen al navegador,
 * porque este código corre del lado del servidor):
 *   GEMINI_API_KEY     -> modo='empresas'
 *   CLAUDE_API_KEY / ANTHROPIC_API_KEY -> el resto
 *   GEMINI_USD_POR_1M_ENTRADA / GEMINI_USD_POR_1M_SALIDA  -> precios (def. 0.75 / 3.75)
 *   CLAUDE_USD_POR_1M_ENTRADA / CLAUDE_USD_POR_1M_SALIDA  -> precios (def. 3 / 15)
 *   BACKEND_URL (o NEXT_PUBLIC_BACKEND_URL)               -> dónde registrar la pregunta
 *
 * Precios por defecto y su fuente (ver `PRECIOS`):
 *   - Gemini 3.6 Flash: US$ 0,75 / 1M tokens de entrada y US$ 3,75 / 1M de
 *     salida, precio estándar vigente hasta el 31-dic-2026 (desde el 1-ene-2027
 *     pasa a 1,50 / 7,50). Fuente: ai.google.dev/gemini-api/docs/pricing,
 *     "Last updated 2026-09-24", consultada el 2026-09-27. Los tokens de
 *     razonamiento (`thoughtsTokenCount`) se facturan como salida y aquí se
 *     suman a la salida.
 *   - Claude Sonnet 4.5: US$ 3 / 1M entrada y US$ 15 / 1M salida (tarifa de la
 *     API de Anthropic para la familia Sonnet 4.x; claude.com/pricing,
 *     consultada el 2026-09-27). No se descuenta el caché de prompts.
 *   Son ESTIMACIONES: la factura real la fija cada proveedor.
 */

import Anthropic from "@anthropic-ai/sdk";
import { NextRequest, NextResponse } from "next/server";
import { MARCADOR_USO, type UsoRespuesta } from "@/lib/chat-sesion";

const GEMINI_MODEL = "gemini-3.6-flash";
const CLAUDE_MODEL = "claude-sonnet-4-5";

const BACKEND_URL =
  process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type Turno = { role: "user" | "assistant"; content: string };

// ---------------------------------------------------------------------------
// Precios por millón de tokens (USD). Configurables por entorno; los valores
// por defecto y su fuente están en la cabecera del archivo.
// ---------------------------------------------------------------------------
function precio(nombre: string, porDefecto: number): number {
  const v = Number(process.env[nombre]);
  return Number.isFinite(v) && v >= 0 ? v : porDefecto;
}

const PRECIOS = {
  gemini: {
    entrada: precio("GEMINI_USD_POR_1M_ENTRADA", 0.75),
    salida: precio("GEMINI_USD_POR_1M_SALIDA", 3.75),
  },
  claude: {
    entrada: precio("CLAUDE_USD_POR_1M_ENTRADA", 3),
    salida: precio("CLAUDE_USD_POR_1M_SALIDA", 15),
  },
};

function costoUsd(
  precios: { entrada: number; salida: number },
  entrada: number | null,
  salida: number | null,
): number | null {
  if (entrada === null && salida === null) return null;
  const costo = ((entrada ?? 0) * precios.entrada + (salida ?? 0) * precios.salida) / 1_000_000;
  return Math.round(costo * 1e8) / 1e8;
}

/** Datos de la pregunta que se registran en el backend (sin nada personal). */
interface RegistroPregunta {
  pregunta: string;
  pagina: string | undefined;
  categoria: string | undefined;
  sesionId: string | undefined;
}

/**
 * Guarda la pregunta en `POST /asistente/preguntas`. Devuelve si quedó
 * guardada. Nunca lanza y no tarda más de 3 s: la analítica no puede
 * retrasar ni romper la respuesta al usuario.
 */
async function registrarPregunta(reg: RegistroPregunta, uso: Omit<UsoRespuesta, "registrada">): Promise<boolean> {
  try {
    const r = await fetch(`${BACKEND_URL}/asistente/preguntas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pregunta: reg.pregunta.slice(0, 500),
        pagina: reg.pagina,
        categoria: reg.categoria,
        sesion_id: reg.sesionId,
        modelo: uso.modelo,
        tokens_entrada: uso.tokens_entrada,
        tokens_salida: uso.tokens_salida,
        costo_usd_estimado: uso.costo_usd_estimado,
      }),
      signal: AbortSignal.timeout(3000),
    });
    if (!r.ok) return false;
    const d = (await r.json().catch(() => ({}))) as { guardada?: boolean };
    return !!d.guardada;
  } catch {
    return false;
  }
}

/** Serializa el tráiler de uso que va al final del stream de texto. */
function trailerUso(uso: UsoRespuesta): Uint8Array {
  return new TextEncoder().encode(MARCADOR_USO + JSON.stringify(uso));
}

/** Un id de sesión válido es corto y opaco; cualquier otra cosa se ignora. */
function sesionValida(v: unknown): string | undefined {
  return typeof v === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(v) ? v : undefined;
}

export async function POST(req: NextRequest) {
  try {
    const { message, pageTitle, pageContent, modo, history, sessionId } = await req.json();

    if (!message) {
      return NextResponse.json(
        { error: "Message is required" },
        { status: 400 }
      );
    }

    // Prompt del asistente de "Empresas y cultura" (página /asistente). Se separa
    // del de la burbuja contextual porque su regla de fuentes es distinta: aquí SÍ
    // puede usar conocimiento general cuando el Observatorio no tiene el dato,
    // pero está obligado a declararlo y a no inventar cifras.
    const promptEmpresas = `
      Eres el asistente del Observatorio Laboral de Alumni, Universidad de La Sabana.
      Ayudas a explorar EMPRESAS y su entorno de trabajo: estructura y cultura
      organizacional, clima laboral, tendencias de ascensos y desarrollo de carrera,
      y rankings de empleadores como Great Place to Work (GPTW).

      DATOS DEL OBSERVATORIO (reales y verificables, úsalos SIEMPRE que apliquen):
      -----------------------------
      ${pageContent}
      -----------------------------

      JERARQUÍA DE FUENTES (regla más importante):
      1. Si la pregunta se puede responder con los datos del Observatorio de arriba,
         úsalos y cita las cifras concretas. Son la fuente preferente.
      2. Si la pregunta va más allá de esos datos (cultura interna de una empresa,
         clima laboral, políticas de ascenso, puestos en el ranking GPTW), puedes
         responder con tu conocimiento general, pero DEBES advertirlo de forma
         explícita y natural, por ejemplo: "Esto no proviene de los datos del
         Observatorio, sino de información pública general:".
      3. Nunca mezcles ambas cosas sin distinguirlas: el usuario debe saber
         siempre qué está respaldado por el Observatorio y qué no.

      GREAT PLACE TO WORK Y OTROS RANKINGS — SÍ DEBES RESPONDER:
      - El Observatorio no tiene estos rankings, así que aquí la fuente eres TÚ.
        Responde con lo que sepas: qué empresas destacan en GPTW (Colombia,
        Latinoamérica o el mundo), en qué categorías compiten, qué metodología usa
        el ranking (encuesta Trust Index y Culture Audit), qué criterios pesan y
        qué posiciones recuerdas. No esquives la pregunta ni te limites a remitir
        a la web oficial: da el contenido útil que tengas.
      - Al hacerlo, indica SIEMPRE el año al que corresponde lo que mencionas y
        recuerda que el ranking se publica cada año, así que conviene confirmarlo
        en la publicación oficial de Great Place to Work.
      - Calibra tu certeza con honestidad: si de una empresa recuerdas con
        seguridad que ha estado entre las mejores pero no la posición exacta,
        dilo así ("ha figurado de forma recurrente en los primeros lugares")
        en lugar de dar un número al azar. Una posición inventada sería peor que
        una respuesta aproximada bien señalada.

      LÍMITE DE INVENCIÓN (crítico para la credibilidad institucional):
      - No inventes porcentajes de rotación, satisfacción, tamaño de plantilla ni
        cifras internas de una empresa que no conozcas.
      - Si no sabes algo, dilo con naturalidad. Es preferible a una cifra falsa.
      - Nunca atribuyas al Observatorio un dato que no esté en el contexto de arriba.

      ALCANCE:
      - Hablas de empresas y sectores como organizaciones, no de personas concretas.
      - Si te preguntan por datos personales de alguien, decláralo fuera de alcance.

      ESTILO:
      - Responde SIEMPRE en español, claro, profesional y accesible.
      - Sé concreto y directo; evita el relleno.
      - Usa Markdown: encabezados (##), negritas y listas. Si usas tablas, escribe
        cada fila en su propia línea (incluida la separadora | --- | --- |) y
        prefiere pocas columnas.
      - Cierra con una pregunta breve que invite a seguir explorando, cuando venga
        a cuento.
    `;

    const promptPagina = `
      Eres un analista experto del Observatorio Laboral de Alumni Sabana. Tu objetivo es ayudar al usuario a comprender, interpretar y extraer valor de los datos, gráficos o reportes que está viendo actualmente en la plataforma.

      El usuario está viendo la siguiente sección: "${pageTitle}"

      A continuación, tienes el contenido exacto y el contexto de lo que el usuario tiene en su pantalla:
      -----------------------------
      ${pageContent}
      -----------------------------

      Normas de respuesta obligatorias:
      - No uses fuentes externas, estimaciones fuera de este contexto ni busques información en internet. Limítate estrictamente a interpretar, estructurar y dar contexto a la información que se te ha proporcionado arriba. Si el contexto no contiene datos suficientes para responder algo, indícalo con amabilidad.
      - El contexto puede incluir DATOS NUMÉRICOS reales (conteos por cargo, sector, ciudad, empresa, rangos salariales, etc.). Cuando existan, ÚSALOS: cita cifras concretas, nombra los valores más altos y bajos, y haz cálculos derivados de esos números (porcentajes, proporciones, totales, comparaciones entre categorías). No inventes números que no estén en el contexto.
      - Recuerda que las cifras son valores AGREGADOS (por ejemplo, los 15-20 cargos más frecuentes), no la totalidad de las vacantes; no afirmes que representan el 100% del mercado.
      - Responde siempre en español, con un lenguaje claro, sencillo y profesional.
      - No uses palabras complejas ni técnicas innecesarias. Explica todo de forma que cualquier persona pueda entenderlo fácilmente a la primera lectura.
      - Sé preciso, concreto y directo. Evita el relleno y las repeticiones.
      - Cada respuesta debe ser un análisis correcto, completo y bien desarrollado basado únicamente en el contenido de la página.

      Estilo de escritura:
      - Usa un tono profesional pero muy accesible y amigable, como explicándole a un profesional inteligente que está navegando la plataforma y quiere entender rápidamente qué significan esos datos.
      - Prioriza la claridad y la simplicidad sin perder profundidad ni calidad en el análisis.

      Regla clave sobre competencias y habilidades:
      - Cuando el contenido de la página mencione competencias (habilidades, conocimientos y aptitudes), sé muy específico al describirlas.
      - Usa listas o tablas para separar competencias técnicas, competencias transversales (blandas) y certificaciones siempre que la información provista lo permita.

      Estructura recomendada (adáptala de forma natural según lo que el usuario esté consultando):

      - **Resumen Principal**: Un bloque corto (2-4 líneas) con los hallazgos, conclusiones o lecturas más importantes de lo que se muestra en la pantalla.
      - **Análisis de la Situación Actual**: Desglose detallado de las cifras, datos o métricas visibles.
      - **Lectura de Competencias Clave**: Sección dedicada a mapear las habilidades técnicas y blandas que aparecen en el contenido, estructuradas de forma scannable.

      Reglas adicionales:
      - Los títulos deben ser claros, directos y en lenguaje cotidiano.
      - Formato Markdown: usa encabezados (##), negritas y listas para que la respuesta sea fácil de leer. Si usas una tabla, ESCRIBE CADA FILA EN SU PROPIA LÍNEA, incluida la fila separadora (| --- | --- |), nunca todo en un mismo renglón. Como el panel de chat es angosto, prefiere tablas de pocas columnas (2-3); si hay muchos datos, usa listas en lugar de tablas anchas.
    `;

    // 'empresas' = página /asistente (chat con conversación, ahora en Gemini).
    // Cualquier otro valor mantiene el comportamiento original de la burbuja
    // contextual (FloatingChat, en Claude).
    const esEmpresas = modo === "empresas";
    const systemPrompt = esEmpresas ? promptEmpresas : promptPagina;

    // El historial se reenvía para que el modelo tenga memoria de los turnos
    // anteriores. La burbuja contextual sigue enviando una sola pregunta suelta.
    const historial: Turno[] = Array.isArray(history)
      ? history
          .filter(
            (h: unknown): h is Turno =>
              !!h &&
              typeof (h as Turno).content === "string" &&
              (h as Turno).content.trim() !== "" &&
              ((h as Turno).role === "user" || (h as Turno).role === "assistant"),
          )
          .slice(-20) // tope de turnos: evita prompts gigantes en charlas largas
      : [];

    // Lo que se registra de la pregunta: texto, página (de ella sale la
    // categoría en el backend) y el id de sesión opaco del navegador.
    const registro: RegistroPregunta = {
      pregunta: String(message),
      pagina: typeof pageTitle === "string" ? pageTitle.slice(0, 120) : undefined,
      categoria: esEmpresas ? "empresas" : undefined,
      sesionId: sesionValida(sessionId),
    };

    return esEmpresas
      ? await responderConGemini(systemPrompt, historial, message, registro)
      : await responderConClaude(systemPrompt, historial, message, registro);
  } catch (error) {
    console.error("Error calling chat API:", error);
    const errorMessage = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Failed to process request: ${errorMessage}` },
      { status: 500 }
    );
  }
}

// ---------------------------------------------------------------------------
// Claude (Anthropic) — burbuja contextual (floating-chat.tsx)
// ---------------------------------------------------------------------------
async function responderConClaude(
  systemPrompt: string,
  historial: Turno[],
  message: string,
  registro: RegistroPregunta,
): Promise<Response> {
  const apiKey = process.env.CLAUDE_API_KEY || process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    console.error("CLAUDE_API_KEY / ANTHROPIC_API_KEY no está configurada");
    return NextResponse.json(
      { error: "API key not configured" },
      { status: 500 }
    );
  }

  const client = new Anthropic({ apiKey });

  console.log("Enviando solicitud a Claude (streaming)...");
  // Usamos streaming para devolver el texto a medida que el modelo lo genera,
  // en vez de esperar la respuesta completa. `system` define el rol/reglas;
  // `messages` lleva la pregunta. Para cambiar de modelo, ajusta `model`.
  const claudeStream = client.messages.stream({
    model: CLAUDE_MODEL,
    max_tokens: 8192,
    system: systemPrompt,
    messages: [...historial, { role: "user", content: message }],
  });

  const encoder = new TextEncoder();
  const readable = new ReadableStream<Uint8Array>({
    async start(controller) {
      let huboTexto = false;
      try {
        for await (const event of claudeStream) {
          if (
            event.type === "content_block_delta" &&
            event.delta.type === "text_delta"
          ) {
            huboTexto = true;
            controller.enqueue(encoder.encode(event.delta.text));
          }
        }
        // Tokens reales del turno: el SDK los acumula en el mensaje final
        // (`usage.input_tokens` / `usage.output_tokens`).
        let entrada: number | null = null;
        let salida: number | null = null;
        try {
          const final = await claudeStream.finalMessage();
          entrada = final.usage?.input_tokens ?? null;
          salida = final.usage?.output_tokens ?? null;
        } catch {
          /* sin usage: se registra la pregunta igual, sin tokens */
        }
        const uso: UsoRespuesta = {
          modelo: CLAUDE_MODEL,
          tokens_entrada: entrada,
          tokens_salida: salida,
          costo_usd_estimado: costoUsd(PRECIOS.claude, entrada, salida),
          estimado: true,
        };
        uso.registrada = await registrarPregunta(registro, uso);
        controller.enqueue(trailerUso(uso));
        controller.close();
      } catch (err) {
        // La respuesta ya salió con 200, así que aquí no se puede cambiar el
        // código HTTP: si se abortara el stream sin más, el usuario solo vería
        // una burbuja vacía. En su lugar se escribe el motivo como texto, que
        // es lo que el frontend ya sabe mostrar.
        console.error("Error durante el streaming de Claude:", err);
        if (!huboTexto) {
          const detalle = err instanceof Error ? err.message : String(err);
          const sinSaldo = /credit balance|quota|billing/i.test(detalle);
          const mensaje = sinSaldo
            ? "No se pudo generar la respuesta: la cuenta de Anthropic no tiene saldo disponible. Revisa *Plans & Billing* en console.anthropic.com y vuelve a intentarlo."
            : `No se pudo generar la respuesta: ${detalle}`;
          controller.enqueue(encoder.encode(mensaje));
        }
        controller.close();
      }
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}

// ---------------------------------------------------------------------------
// Gemini (Google) — chat de Empresas y cultura (/asistente)
// ---------------------------------------------------------------------------

/** Un evento `data: {...}` del stream SSE de Gemini. Solo se leen los campos usados. */
interface GeminiChunk {
  candidates?: {
    content?: { parts?: { text?: string }[] };
    finishReason?: string;
  }[];
  // Gemini incluye el conteo de tokens en los chunks (el último trae el total
  // definitivo). `thoughtsTokenCount` son los tokens de razonamiento de los
  // modelos con "thinking": se facturan como salida.
  usageMetadata?: {
    promptTokenCount?: number;
    candidatesTokenCount?: number;
    thoughtsTokenCount?: number;
    totalTokenCount?: number;
  };
  error?: { message?: string; status?: string };
}

async function responderConGemini(
  systemPrompt: string,
  historial: Turno[],
  message: string,
  registro: RegistroPregunta,
): Promise<Response> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    console.error("GEMINI_API_KEY no está configurada");
    return NextResponse.json(
      { error: "API key not configured" },
      { status: 500 }
    );
  }

  // Gemini usa 'model' donde Claude usa 'assistant'; el resto del formato de
  // turno (role + texto) es equivalente.
  const contents = [
    ...historial.map((h) => ({
      role: h.role === "assistant" ? "model" : "user",
      parts: [{ text: h.content }],
    })),
    { role: "user", parts: [{ text: message }] },
  ];

  console.log("Enviando solicitud a Gemini (streaming)...");
  const url =
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:streamGenerateContent` +
    `?alt=sse&key=${apiKey}`;

  const geminiResponse = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      system_instruction: { parts: [{ text: systemPrompt }] },
      contents,
      generationConfig: { maxOutputTokens: 8192 },
    }),
  });

  const encoder = new TextEncoder();

  // Fallo antes de empezar a transmitir (auth, cuota, modelo inválido...): sí se
  // puede devolver un código de error real, a diferencia del caso de streaming
  // ya iniciado.
  if (!geminiResponse.ok || !geminiResponse.body) {
    const detalle = await geminiResponse.text().catch(() => "");
    console.error("Error de Gemini antes de transmitir:", geminiResponse.status, detalle);
    const sinCuota = geminiResponse.status === 429 || /quota|RESOURCE_EXHAUSTED/i.test(detalle);
    const mensaje = sinCuota
      ? "No se pudo generar la respuesta: se agotó la cuota de la API de Gemini. Revisa el plan en Google AI Studio y vuelve a intentarlo."
      : `No se pudo generar la respuesta: ${geminiResponse.status} ${detalle.slice(0, 300)}`;
    return new Response(mensaje, {
      status: 200, // el frontend espera texto plano y lo muestra tal cual
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  // El endpoint con alt=sse entrega líneas "data: {...}\n\n". Se parsean y se
  // reempaqueta SOLO el texto, para mantener el mismo contrato de salida
  // (texto plano) que ya consume el frontend, sin importar qué modelo respondió.
  const readable = new ReadableStream<Uint8Array>({
    async start(controller) {
      const reader = geminiResponse.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let huboTexto = false;
      // Último `usageMetadata` visto: Gemini lo repite y el final es el total.
      let usage: GeminiChunk["usageMetadata"] | undefined;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lineas = buffer.split("\n");
          buffer = lineas.pop() ?? ""; // última línea puede venir incompleta

          for (const linea of lineas) {
            const l = linea.trim();
            if (!l.startsWith("data:")) continue;
            const json = l.slice(5).trim();
            if (!json) continue;
            try {
              const chunk: GeminiChunk = JSON.parse(json);
              if (chunk.error) {
                throw new Error(chunk.error.message || chunk.error.status || "Error de Gemini");
              }
              if (chunk.usageMetadata) usage = chunk.usageMetadata;
              const texto = chunk.candidates?.[0]?.content?.parts?.[0]?.text;
              if (texto) {
                huboTexto = true;
                controller.enqueue(encoder.encode(texto));
              }
            } catch {
              // Fragmento SSE incompleto o no-JSON: se ignora, no es fatal.
            }
          }
        }
        const entrada = usage?.promptTokenCount ?? null;
        const salida =
          usage && (usage.candidatesTokenCount !== undefined || usage.thoughtsTokenCount !== undefined)
            ? (usage.candidatesTokenCount ?? 0) + (usage.thoughtsTokenCount ?? 0)
            : null;
        const uso: UsoRespuesta = {
          modelo: GEMINI_MODEL,
          tokens_entrada: entrada,
          tokens_salida: salida,
          costo_usd_estimado: costoUsd(PRECIOS.gemini, entrada, salida),
          estimado: true,
        };
        uso.registrada = await registrarPregunta(registro, uso);
        controller.enqueue(trailerUso(uso));
        controller.close();
      } catch (err) {
        console.error("Error durante el streaming de Gemini:", err);
        if (!huboTexto) {
          const detalle = err instanceof Error ? err.message : String(err);
          controller.enqueue(encoder.encode(`No se pudo generar la respuesta: ${detalle}`));
        }
        controller.close();
      }
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}
