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
 * Las API keys se leen de variables de entorno (nunca se exponen al navegador,
 * porque este código corre del lado del servidor):
 *   GEMINI_API_KEY     -> modo='empresas'
 *   CLAUDE_API_KEY / ANTHROPIC_API_KEY -> el resto
 *
 * NOTA: el proyecto se exporta como sitio estático (next.config.ts -> output:
 * 'export'), modo en el que las rutas API de Next no se ejecutan como servidor.
 * Para que el chat funcione en producción se requiere un entorno que sí ejecute
 * esta ruta (verificar el hosting al desplegar).
 */

import Anthropic from "@anthropic-ai/sdk";
import { NextRequest, NextResponse } from "next/server";

const GEMINI_MODEL = "gemini-3.6-flash";

type Turno = { role: "user" | "assistant"; content: string };

export async function POST(req: NextRequest) {
  try {
    const { message, pageTitle, pageContent, modo, history } = await req.json();

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

    return esEmpresas
      ? await responderConGemini(systemPrompt, historial, message)
      : await responderConClaude(systemPrompt, historial, message);
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
    model: "claude-sonnet-4-5",
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
  error?: { message?: string; status?: string };
}

async function responderConGemini(
  systemPrompt: string,
  historial: Turno[],
  message: string,
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
