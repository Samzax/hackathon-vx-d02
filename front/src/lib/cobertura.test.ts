import { describe, expect, it } from "vitest";
import { CLASSES, confianca, fonteLida, rotuloDaCobertura, tomDaCobertura } from "./cobertura";

describe("cobertura normativa", () => {
  it("coberta é verde, o que espera é amarelo, sem fonte é cinza", () => {
    expect(tomDaCobertura("coberta", true)).toBe("verde");
    for (const e of ["triagem_pendente", "curadoria_pendente", "extracao_pendente"]) expect(tomDaCobertura(e, true)).toBe("amarelo");
    expect(tomDaCobertura("sem_fonte", false)).toBe("cinza");
    expect(tomDaCobertura("nao_buscada", false)).toBe("cinza");
    expect(CLASSES.verde.etiqueta).toBe("ok");
    expect(CLASSES.cinza.etiqueta).toBe("neutro");
  });

  it("o que não foi verificado nunca sai verde, nem com estado que a tela não conhece", () => {
    expect(tomDaCobertura("coberta", false)).toBe("cinza");
    expect(tomDaCobertura("estado_novo", true)).toBe("cinza");
    expect(rotuloDaCobertura("fonte ainda não lida", false)).toBe("fonte ainda não lida: cobertura não verificada");
    expect(rotuloDaCobertura("sem fonte automática: cobertura não verificada", false)).toBe("sem fonte automática: cobertura não verificada");
    expect(rotuloDaCobertura("normas relevantes esperando a curadoria", true)).toBe("normas relevantes esperando a curadoria");
  });

  it("fonte lida com os anos e o dia em Brasília", () => {
    expect(fonteLida({ nome: "Assembleia de Minas", desde: 1989, ate: 2026, em: "2026-11-07 00:52:34" }))
      .toBe("Assembleia de Minas, 1989–2026, lida em 06/11/2026");
    expect(fonteLida({ nome: "ANMlegis (ANM)", desde: 2026, ate: 2026, em: "2026-11-07 12:00:00" }))
      .toBe("ANMlegis (ANM), 2026, lida em 07/11/2026");
    expect(confianca(0.96)).toBe("0,96");
  });
});
