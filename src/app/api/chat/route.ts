/**
 * Ruta API del asistente de IA (proxy hacia Claude / Anthropic).
 *
 * Recibe del frontend (floating-chat.tsx) la pregunta del usuario más el contexto
 * de la página actual (pageTitle + pageContent), arma un "system prompt" que
 * obliga a Claude a responder SOLO con base en ese contexto, y devuelve la
 * respuesta en texto.
 *
 * La API key se lee de la variable de entorno CLAUDE_API_KEY (nunca se expone al
 * navegador, porque este código corre del lado del servidor).
 *
 * NOTA: el proyecto se exporta como sitio estático (next.config.ts -> output:
 * 'export'), modo en el que las rutas API de Next no se ejecutan como servidor.
 * Para que el chat funcione en producción se requiere un entorno que sí ejecute
 * esta ruta (verificar el hosting al desplegar).
 */

import Anthropic from "@anthropic-ai/sdk";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    // Verificar que la API key está disponible
    const apiKey = process.env.CLAUDE_API_KEY;
    if (!apiKey) {
      console.error("CLAUDE_API_KEY no está configurada");
      return NextResponse.json(
        { error: "API key not configured" },
        { status: 500 }
      );
    }

    const { message, pageTitle, pageContent } = await req.json();

    if (!message) {
      return NextResponse.json(
        { error: "Message is required" },
        { status: 400 }
      );
    }

    const client = new Anthropic({
      apiKey: apiKey,
    });

    const systemPrompt = `
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

    console.log("Enviando solicitud a Claude (streaming)...");
    // Usamos streaming para devolver el texto a medida que el modelo lo genera,
    // en vez de esperar la respuesta completa. `system` define el rol/reglas;
    // `messages` lleva la pregunta. Para cambiar de modelo, ajusta `model`.
    const claudeStream = client.messages.stream({
      model: "claude-sonnet-4-5",
      max_tokens: 8192,
      system: systemPrompt,
      messages: [
        {
          role: "user",
          content: message,
        },
      ],
    });

    // Reempaquetamos los eventos del SDK en un stream de TEXTO PLANO: solo los
    // fragmentos de texto, que es lo que el frontend va concatenando y mostrando.
    const encoder = new TextEncoder();
    const readable = new ReadableStream<Uint8Array>({
      async start(controller) {
        try {
          for await (const event of claudeStream) {
            if (
              event.type === "content_block_delta" &&
              event.delta.type === "text_delta"
            ) {
              controller.enqueue(encoder.encode(event.delta.text));
            }
          }
          controller.close();
        } catch (err) {
          controller.error(err);
        }
      },
    });

    return new Response(readable, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        // Evita que proxies/buffers retengan el stream antes de mostrarlo.
        "Cache-Control": "no-cache, no-transform",
      },
    });
  } catch (error) {
    console.error("Error calling Claude API:", error);
    const errorMessage = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Failed to process request: ${errorMessage}` },
      { status: 500 }
    );
  }
}
