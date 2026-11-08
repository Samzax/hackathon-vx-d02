// Assistente Mitra: o que a tela precisa além da chamada (sugestões, rótulos, histórico e conferência).
import type { Esquemas } from "./api";

export type RespostaPergunta = Esquemas["RespostaPergunta"];
export type Conferencia = RespostaPergunta["conferencia"];

export type MensagemChat =
  | { papel: "usuario"; texto: string }
  | { papel: "torre"; texto: string; resposta: RespostaPergunta }
  | { papel: "erro"; texto: string };

/** Perguntas que a demo responde bem, uma por tipo de roteiro do modelo. */
export const SUGESTOES = [
  "O que está atrasado hoje e o que faço primeiro?",
  "O que está atrasado na B3 e por qual artigo?",
  "Alguma norma mudou? O que preciso decidir?",
  "O que passa a valer quando a Res. ANM 220/2025 entrar em vigor?",
  "Que normas valem para as minhas barragens em Minas Gerais?",
  "Como está o vaso de pressão VP-101?",
];

export const ROTULO_FERRAMENTA: Record<string, string> = {
  empresas: "empresas",
  pendencias: "pendências",
  ativos: "ativos",
  ficha_do_ativo: "ficha do ativo",
  obrigacoes: "catálogo de obrigações",
  historico_da_obrigacao: "histórico da obrigação",
  mudancas_pendentes: "mudanças aguardando decisão",
  linha_do_tempo: "linha do tempo",
  boletim: "boletim",
  cobertura_normativa: "cobertura normativa",
  radar_do_dou: "radar",
};

export const MAX_HISTORICO = 8;

/** A conversa que vai para a API: só perguntas e respostas (erro de rede não entra), as últimas. */
export function historicoPara(msgs: MensagemChat[], max = MAX_HISTORICO): { papel: "usuario" | "torre"; texto: string }[] {
  return msgs
    .filter((m): m is Exclude<MensagemChat, { papel: "erro" }> => m.papel !== "erro")
    .slice(-max)
    .map((m) => ({ papel: m.papel, texto: m.texto }));
}

/** Ferramentas consultadas, sem repetir, na ordem em que o modelo chamou. */
export function consultas(r: RespostaPergunta): string[] {
  const vistas: string[] = [];
  for (const u of r.ferramentas) {
    const rotulo = ROTULO_FERRAMENTA[u.ferramenta] ?? u.ferramenta;
    if (!u.erro && !vistas.includes(rotulo)) vistas.push(rotulo);
  }
  return vistas;
}

/** O selo da conferência do Python: o que a resposta afirma com aspas, data ou código bate com a torre? */
export function resumoConferencia(c: Conferencia): { ok: boolean; texto: string; fora: string[] } {
  const fora = [
    ...c.citacoes_fora.map((t) => `trecho "${t}"`),
    ...c.datas_fora.map((d) => `data ${d}`),
    ...c.codigos_fora.map((x) => `código ${x}`),
  ];
  if (c.ok) {
    const trechos = c.citacoes === 1 ? "1 trecho citado" : `${c.citacoes} trechos citados`;
    return { ok: true, texto: `Conferido: ${c.citacoes ? `${trechos}, ` : ""}datas e códigos batem com a torre`, fora };
  }
  return { ok: false, texto: "Parte da resposta não bate com a torre: confira antes de usar", fora };
}
