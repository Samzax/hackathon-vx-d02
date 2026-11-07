import { describe, expect, it } from "vitest";
import { atributosDoRascunho, cnpjBR, etapasProntas, resumoPlanilha, ufsDeTexto } from "./instanciacao";
import type { EstadoInstanciacao, Planilha } from "./instanciacao";

describe("cnpjBR", () => {
  it("formata 14 dígitos e deixa o resto como veio", () => {
    expect(cnpjBR("11222333000181")).toBe("11.222.333/0001-81");
    expect(cnpjBR("11.222.333/0001-81")).toBe("11.222.333/0001-81");
    expect(cnpjBR("123")).toBe("123");
    expect(cnpjBR(null)).toBe("não informado");
  });
});

describe("ufsDeTexto", () => {
  it("aceita vírgula, espaço e minúscula, sem repetir", () => {
    expect(ufsDeTexto("mg, pr sp;mg")).toEqual({ ufs: ["MG", "PR", "SP"], erro: null });
    expect(ufsDeTexto("")).toEqual({ ufs: [], erro: null });
  });
  it("sigla que não é UF volta como erro, sem adivinhar", () => {
    const r = ufsDeTexto("MG, XX");
    expect(r.ufs).toEqual([]);
    expect(r.erro).toContain("XX");
  });
});

describe("atributosDoRascunho", () => {
  it("campo vazio fica de fora: não informado nunca vira valor", () => {
    expect(atributosDoRascunho({ uf: " PR ", altura_m: "", dpa: "alto" })).toEqual({ uf: "PR", dpa: "alto" });
    expect(atributosDoRascunho({})).toEqual({});
  });
});

describe("resumoPlanilha", () => {
  const base = (erros: number, importados: number, n: number): Planilha => ({
    erros,
    importados,
    linhas: Array.from({ length: n }, (_, i) => ({
      linha: i + 2, tipo: "barragem", codigo: `B${i}`, nome: `B${i}`, unidade: null, responsavel: null,
      atributos: {}, erro: i === 0 && erros ? "uf: não é UF" : null,
    })),
  });
  it("erro em qualquer linha: nada foi gravado", () => {
    expect(resumoPlanilha(base(1, 0, 3), false)).toContain("nada foi gravado");
  });
  it("conferir não grava; importar conta os ativos", () => {
    expect(resumoPlanilha(base(0, 0, 2), true)).toBe("2 linhas boas: pode importar.");
    expect(resumoPlanilha(base(0, 2, 2), false)).toBe("2 ativos importados.");
  });
});

describe("etapasProntas", () => {
  it("conta as prontas sobre o total", () => {
    const estado = {
      etapas: [{ estado: "pronta" }, { estado: "pendente" }, { estado: "em_andamento" }],
    } as unknown as EstadoInstanciacao;
    expect(etapasProntas(estado)).toEqual({ prontas: 1, total: 3 });
  });
});
