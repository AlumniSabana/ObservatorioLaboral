import { describe, expect, it } from 'vitest';
import {
  MARCADOR_USO,
  formatearTokens,
  formatearUsd,
  obtenerSesionId,
  separarUso,
} from '../chat-sesion';

describe('separarUso', () => {
  it('sin tráiler devuelve todo el texto y uso nulo', () => {
    expect(separarUso('Hola')).toEqual({ texto: 'Hola', uso: null });
  });

  it('parte el texto visible del JSON de uso', () => {
    const uso = { modelo: 'm', tokens_entrada: 10, tokens_salida: 5, costo_usd_estimado: 0.001, estimado: true };
    const r = separarUso(`Respuesta${MARCADOR_USO}${JSON.stringify(uso)}`);
    expect(r.texto).toBe('Respuesta');
    expect(r.uso?.tokens_entrada).toBe(10);
  });

  it('con el JSON a medias espera al siguiente fragmento sin perder texto', () => {
    const r = separarUso(`Respuesta${MARCADOR_USO}{"modelo":"m"`);
    expect(r).toEqual({ texto: 'Respuesta', uso: null });
  });
});

describe('formato', () => {
  it('USD y tokens muestran guion cuando no hay dato', () => {
    expect(formatearUsd(null)).toBe('—');
    expect(formatearUsd(undefined)).toBe('—');
    expect(formatearTokens(null)).toBe('—');
  });

  it('USD respeta los decimales pedidos', () => {
    expect(formatearUsd(0.5)).toBe('US$ 0.5000');
    expect(formatearUsd(1.23456, 2)).toBe('US$ 1.23');
  });
});

describe('obtenerSesionId', () => {
  it('es estable dentro de la misma pestaña', () => {
    const a = obtenerSesionId();
    expect(a.length).toBeGreaterThan(8);
    expect(obtenerSesionId()).toBe(a);
  });
});
