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

    const systemPrompt = `You are a helpful assistant for the Alumni Sabana Labor Observatory platform. 
    The user is currently viewing: "${pageTitle}"
    
    Context about what the user is viewing:
    ${pageContent}
    
    Provide clear, concise interpretations and insights related to what they're viewing. 
    Answer in Spanish since this is a Spanish platform.
    Be professional but friendly.`;

    console.log("Enviando solicitud a Claude...");
    const message_response = await client.messages.create({
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

    const responseText =
      message_response.content[0]?.type === "text"
        ? message_response.content[0].text
        : "No response generated";

    return NextResponse.json({
      response: responseText,
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
