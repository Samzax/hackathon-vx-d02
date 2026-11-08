import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ATRASADA, DADO_FALTANDO, EM_DIA, GATILHO, ROTULO, VENCE_LOGO, cor, ordenar, orgao, pior } from "./status";

describe("status", () => {
  it("apresenta os rótulos atualizados dos status", () => {
    expect(ROTULO[DADO_FALTANDO]).toBe("Cadastro Incompleto");
    expect(ROTULO[VENCE_LOGO]).toBe("Próximo ao vencimento");
  });

  it("o pior status manda na cor do ativo", () => {
    expect(pior({ atrasada: 1, dado_faltando: 2 })).toBe(ATRASADA);
    expect(pior({ dado_faltando: 1, vence_logo: 3 })).toBe(DADO_FALTANDO);
    expect(pior({ vence_logo: 1, em_dia: 9 })).toBe(VENCE_LOGO);
    expect(pior({ em_dia: 9, gatilho: 8 })).toBe(EM_DIA);
    expect(pior({})).toBe(EM_DIA);
  });

  it("cada status tem a sua cor: vermelho, lilás, amarelo, verde, azul", () => {
    expect(cor(ATRASADA).hex).toBe("var(--atrasada)");
    expect(cor(DADO_FALTANDO).hex).toBe("var(--faltando)");
    expect(cor(VENCE_LOGO).hex).toBe("var(--vence-marca)");
    expect(cor(EM_DIA).hex).toBe("var(--emdia)");
    expect(cor(GATILHO).hex).toBe("var(--gatilho)");
    const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf-8");
    for (const v of ["--atrasada", "--faltando", "--vence-marca", "--emdia", "--gatilho"]) {
      expect(css.match(new RegExp(`${v}:`, "g"))?.length, v).toBeGreaterThanOrEqual(2); // claro e escuro
    }
  });

  it("ordena como a torre: status, vencimento, ativo", () => {
    const l = ordenar([
      { status: EM_DIA, vence: "2026-11-15", ativo: "B1" },
      { status: ATRASADA, vence: "2026-10-31", ativo: "E1" },
      { status: ATRASADA, vence: "2026-10-15", ativo: "B3" },
      { status: GATILHO, vence: null, ativo: "A0" },
    ]);
    expect(l.map((x) => x.ativo)).toEqual(["B3", "E1", "B1", "A0"]);
  });

  it("órgão pela norma", () => {
    expect(orgao("Res. ANM 95/2022")).toBe("ANM");
    expect(orgao("NR-13")).toBe("MTE");
    expect(orgao("LO 000/2023 (fictícia)")).toBe("Órgão ambiental");
  });
});

describe("marca", () => {
  it("os SVGs do front são os de assets/ (uma fonte só)", () => {
    for (const nome of ["marca.svg", "logo_claro.svg", "logo_escuro.svg"]) {
      const publico = readFileSync(new URL(`../../public/${nome}`, import.meta.url), "utf-8").replace(/\r\n/g, "\n");
      const original = readFileSync(new URL(`../../../assets/${nome}`, import.meta.url), "utf-8").replace(/\r\n/g, "\n");
      expect(publico, nome).toBe(original);
    }
  });
});
