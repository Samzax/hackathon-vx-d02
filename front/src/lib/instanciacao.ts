// A lógica pura da instanciação (tela Nova empresa e ações da tela Instanciação): formato de CNPJ,
// UFs digitadas, atributos do formulário de ativo e o resumo da planilha. A tela só dá forma; as
// regras de verdade (validação campo a campo, etapas) são da API — aqui nada é presumido.
import type { Esquemas } from "./api";

export type EstadoInstanciacao = Esquemas["Estado"];
export type LinhaPlanilha = Esquemas["LinhaPlanilha"];
export type Planilha = Esquemas["Planilha"];

/** Os tipos de ativo do cadastro, na ordem do formulário (o contrato aceita estes cinco). */
export const TIPOS_ATIVO = ["barragem", "unidade", "equipamento", "licenca", "obra"] as const;
export const ROTULO_TIPO: Record<(typeof TIPOS_ATIVO)[number], string> = {
  barragem: "Barragem",
  unidade: "Unidade (mina, usina, pilha)",
  equipamento: "Equipamento (NR-13…)",
  licenca: "Licença",
  obra: "Obra",
};

/** "12345678000199" -> "12.345.678/0001-99"; o que não for CNPJ de 14 dígitos volta como veio. */
export function cnpjBR(cnpj: string | null | undefined): string {
  const d = (cnpj ?? "").replace(/\D/g, "");
  if (d.length !== 14) return cnpj ?? "não informado";
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

const UFS = new Set([
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
  "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]);

/** "mg, pr sp" -> ["MG", "PR", "SP"]; sigla que não é UF volta como erro, sem adivinhar. */
export function ufsDeTexto(texto: string): { ufs: string[]; erro: string | null } {
  const partes = texto.split(/[\s,;]+/).map((p) => p.trim().toUpperCase()).filter(Boolean);
  const ufs = [...new Set(partes)];
  const ruins = ufs.filter((u) => !UFS.has(u));
  if (ruins.length) return { ufs: [], erro: `não é UF: ${ruins.join(", ")}` };
  return { ufs, erro: null };
}

/**
 * O que o formulário preencheu vira os atributos do ativo: campo vazio fica de fora (não informado
 * nunca vira valor). Os valores seguem como texto — quem converte e confere é a API, campo a campo.
 */
export function atributosDoRascunho(rascunho: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [campo, valor] of Object.entries(rascunho)) {
    const v = valor.trim();
    if (v !== "") out[campo] = v;
  }
  return out;
}

/** A frase do resultado da planilha: conferida ou importada, com os erros na conta. */
export function resumoPlanilha(p: Planilha, soConferiu: boolean): string {
  const linhas = p.linhas.length;
  if (p.erros) {
    return `${linhas} ${linhas === 1 ? "linha" : "linhas"}, ${p.erros} com erro: nada foi gravado — corrija e envie de novo.`;
  }
  if (soConferiu) return `${linhas} ${linhas === 1 ? "linha boa" : "linhas boas"}: pode importar.`;
  return `${p.importados} ${p.importados === 1 ? "ativo importado" : "ativos importados"}.`;
}

/** Quantas etapas prontas/total, para a lista de instanciações. */
export function etapasProntas(estado: EstadoInstanciacao): { prontas: number; total: number } {
  return {
    prontas: estado.etapas.filter((e) => e.estado === "pronta").length,
    total: estado.etapas.length,
  };
}
