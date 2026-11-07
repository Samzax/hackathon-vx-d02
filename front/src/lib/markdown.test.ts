import { describe, expect, it } from "vitest";
import { lerMarkdown, trechos } from "./markdown";

describe("markdown do boletim", () => {
  it("negrito, itálico e código dentro da linha", () => {
    expect(trechos("**B3** · vence *amanhã* em `R95-01`")).toEqual([
      { tipo: "negrito", texto: "B3" },
      { tipo: "texto", texto: " · vence " },
      { tipo: "italico", texto: "amanhã" },
      { tipo: "texto", texto: " em " },
      { tipo: "codigo", texto: "R95-01" },
    ]);
  });

  it("asterisco solto não vira itálico", () => {
    expect(trechos("3 * 4 = 12")).toEqual([{ tipo: "texto", texto: "3 * 4 = 12" }]);
  });

  it("títulos, listas com nível e parágrafos", () => {
    const md = "# Boletim — Diretoria\n\nSemana de 07/11/2026.\nSegunda linha.\n\n## Atrasadas\n- **B3** · FIR\n  - antes: Res. 95\n- E1 · exame";
    const b = lerMarkdown(md);
    expect(b.map((x) => x.tipo)).toEqual(["titulo", "paragrafo", "titulo", "lista"]);
    expect(b[0]).toMatchObject({ nivel: 1 });
    expect(b[1]).toEqual({ tipo: "paragrafo", trechos: [{ tipo: "texto", texto: "Semana de 07/11/2026. Segunda linha." }] });
    const lista = b[3] as Extract<(typeof b)[number], { tipo: "lista" }>;
    expect(lista.itens.map((i) => i.nivel)).toEqual([0, 1, 0]);
  });

  it("não interpreta HTML: o texto continua texto", () => {
    const b = lerMarkdown("<script>alert(1)</script>");
    expect(b).toEqual([{ tipo: "paragrafo", trechos: [{ tipo: "texto", texto: "<script>alert(1)</script>" }] }]);
  });
});
