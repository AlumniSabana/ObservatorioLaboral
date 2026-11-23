import { describe, expect, it } from 'vitest';
import { cortar, fechaHoy, rgb } from '../perfil-pdf';

describe('utilidades del PDF', () => {
  it('rgb convierte hex a canales', () => {
    expect(rgb('#002058')).toEqual([0, 32, 88]);
    expect(rgb('ffffff')).toEqual([255, 255, 255]);
  });

  it('cortar deja intacto lo corto y recorta con elipsis lo largo', () => {
    expect(cortar('hola', 10)).toBe('hola');
    const r = cortar('abcdefghij', 5);
    expect(r).toBe('abcd…');
    expect(r.length).toBe(5);
  });

  it('fechaHoy da una fecha legible en español', () => {
    expect(fechaHoy()).toMatch(/\d{4}/);
  });
});
