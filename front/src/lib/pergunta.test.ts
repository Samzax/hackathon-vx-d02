import { describe, expect, it } from "vitest";
import { consultas, historicoPara, type MensagemChat, resumoConferencia, type RespostaPergunta } from "./pergunta";

const conf = (o: Partial<RespostaPergunta["conferencia"]> = {}) => ({
  ok: true, citacoes: 2, citacoes_fora: [], datas_fora: [], codigos_fora: [], ...o,
});

const resposta = (o: Partial<RespostaPergunta> = {}): RespostaPergunta => ({
  texto: "A R95-01 está atrasada.", modelo: "bedrock:us.anthropic.claude-sonnet-5", conferencia: conf(),
  ferramentas: [], tokens_in: 1, tokens_out: 1, tokens_cache: 0, custo_usd: 0.01, corrigida: false, segundos: 8.2, ...o,
});

describe("histórico que vai para a API", () => {
  it("leva só pergunta e resposta, as últimas, sem os erros", () => {
    const msgs: MensagemChat[] = [
      { papel: "usuario", texto: "a" },
      { papel: "erro", texto: "sem conexão" },
      { papel: "usuario", texto: "b" },
      { papel: "torre", texto: "c", resposta: resposta() },
    ];
    expect(historicoPara(msgs)).toEqual([
      { papel: "usuario", texto: "a" }, { papel: "usuario", texto: "b" }, { papel: "torre", texto: "c" },
    ]);
    expect(historicoPara(msgs, 2)).toEqual([{ papel: "usuario", texto: "b" }, { papel: "torre", texto: "c" }]);
  });
});

describe("consultas feitas", () => {
  it("rótulos legíveis, sem repetir e sem as que deram erro", () => {
    const r = resposta({ ferramentas: [
      { ferramenta: "pendencias", args: {} }, { ferramenta: "pendencias", args: { ativo: "B3" } },
      { ferramenta: "ficha_do_ativo", args: { ativo: "B9" }, erro: "não encontrado" },
      { ferramenta: "linha_do_tempo", args: {} },
    ] });
    expect(consultas(r)).toEqual(["pendências", "linha do tempo"]);
  });
});

describe("selo da conferência", () => {
  it("ok diz quantos trechos foram conferidos", () => {
    expect(resumoConferencia(conf())).toMatchObject({ ok: true, texto: expect.stringContaining("2 trechos citados") });
    expect(resumoConferencia(conf({ citacoes: 0 })).texto).toBe("Conferido: datas e códigos batem com a torre");
  });
  it("o que não bate aparece um a um", () => {
    const r = resumoConferencia(conf({ ok: false, citacoes_fora: ["preencher toda semana"], datas_fora: ["2030-01-01"], codigos_fora: ["OB-99"] }));
    expect(r.ok).toBe(false);
    expect(r.fora).toEqual(['trecho "preencher toda semana"', "data 2030-01-01", "código OB-99"]);
  });
});
