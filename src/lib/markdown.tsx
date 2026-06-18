'use client';

/**
 * Renderizado de Markdown para las respuestas de Claude.
 *
 * Lo usan tanto el chat flotante (floating-chat.tsx) como el lector de documentos
 * (document-reader.tsx). Expone <AssistantContent /> que renderiza texto Markdown
 * con estilos pulidos y soporte de TABLAS.
 *
 * Las tablas se parsean a mano (parseBlocks + MarkdownTable) porque react-markdown
 * no soporta tablas GFM sin el plugin remark-gfm (que no está instalado).
 */

import ReactMarkdown, { type Components } from 'react-markdown';

// Estilos por elemento para react-markdown (no usamos clases `prose` porque el
// plugin de tipografía de Tailwind no está instalado).
const mdComponents: Components = {
  h1: ({ children }) => <h1 className="text-base font-bold mt-3 mb-1">{children}</h1>,
  h2: ({ children }) => <h2 className="text-base font-bold mt-3 mb-1">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-bold mt-2 mb-1">{children}</h3>,
  p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="list-disc list-outside mb-2 pl-5 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal list-outside mb-2 pl-5 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-bold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a href={href} className="text-blue-600 dark:text-blue-300 underline" target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-zinc-400 pl-3 italic my-2">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-zinc-300 dark:border-zinc-600" />,
  code: ({ children }) => (
    <code className="bg-zinc-300 dark:bg-zinc-600 px-1 py-0.5 rounded text-[0.8em]">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="bg-zinc-300 dark:bg-zinc-900 rounded p-2 my-2 overflow-x-auto text-xs">{children}</pre>
  ),
};

// Divide el contenido en bloques: tablas Markdown (GFM) vs. el resto.
function parseBlocks(content: string): Array<{ type: 'md' | 'table'; text: string }> {
  const lines = content.split('\n');
  const blocks: Array<{ type: 'md' | 'table'; text: string }> = [];
  let mdBuffer: string[] = [];

  const flushMd = () => {
    if (mdBuffer.length) {
      blocks.push({ type: 'md', text: mdBuffer.join('\n') });
      mdBuffer = [];
    }
  };

  // Una fila separadora se ve como: | --- | :---: | ---: |
  const isSeparator = (line: string) => {
    const t = line.trim();
    if (!t.includes('-') || !t.includes('|')) return false;
    const cells = t.replace(/^\|/, '').replace(/\|$/, '').split('|');
    return cells.length >= 1 && cells.every((c) => /^\s*:?-{1,}:?\s*$/.test(c));
  };
  const isRow = (line: string) => line.includes('|') && line.trim() !== '';

  let i = 0;
  while (i < lines.length) {
    // Una tabla = una fila de encabezado seguida de una fila separadora.
    if (isRow(lines[i]) && i + 1 < lines.length && isSeparator(lines[i + 1])) {
      flushMd();
      const tableLines = [lines[i], lines[i + 1]];
      i += 2;
      while (i < lines.length && isRow(lines[i])) {
        tableLines.push(lines[i]);
        i++;
      }
      blocks.push({ type: 'table', text: tableLines.join('\n') });
    } else {
      mdBuffer.push(lines[i]);
      i++;
    }
  }
  flushMd();
  return blocks;
}

// Renderiza un bloque de tabla Markdown como una tabla HTML con estilo.
function MarkdownTable({ text }: { text: string }) {
  const rows = text.split('\n').filter((l) => l.trim() !== '');
  if (rows.length < 2) return <p>{text}</p>;

  const splitRow = (line: string) => {
    let t = line.trim();
    if (t.startsWith('|')) t = t.slice(1);
    if (t.endsWith('|')) t = t.slice(0, -1);
    return t.split('|').map((c) => c.trim());
  };

  const header = splitRow(rows[0]);
  const bodyRows = rows.slice(2).map(splitRow); // saltamos la fila separadora (índice 1)

  return (
    <div className="overflow-x-auto my-2">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            {header.map((cell, idx) => (
              <th
                key={idx}
                className="border border-zinc-400 dark:border-zinc-500 px-2 py-1 text-left font-bold bg-zinc-300 dark:bg-zinc-600"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((cells, r) => (
            <tr key={r}>
              {cells.map((cell, c) => (
                <td key={c} className="border border-zinc-400 dark:border-zinc-500 px-2 py-1 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Renderiza el contenido completo de un mensaje del asistente: intercala
// segmentos de Markdown normal con tablas renderizadas a mano.
export function AssistantContent({ content }: { content: string }) {
  const blocks = parseBlocks(content);
  return (
    <div className="text-sm leading-relaxed">
      {blocks.map((block, idx) =>
        block.type === 'table' ? (
          <MarkdownTable key={idx} text={block.text} />
        ) : (
          <ReactMarkdown key={idx} components={mdComponents}>
            {block.text}
          </ReactMarkdown>
        ),
      )}
    </div>
  );
}
