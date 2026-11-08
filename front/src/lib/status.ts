// Os status das obrigações e as cores da torre: atrasada vermelho, dado faltando lilás,
// vence em breve amarelo, em dia verde, por gatilho azul. Cor só onde tem significado.

export const ATRASADA = "atrasada";
export const DADO_FALTANDO = "dado_faltando";
export const VENCE_LOGO = "vence_logo";
export const EM_DIA = "em_dia";
export const CUMPRIDA = "cumprida";
export const GATILHO = "gatilho";

/** Os cinco números do topo, nesta ordem. */
export const PRINCIPAIS = [ATRASADA, DADO_FALTANDO, VENCE_LOGO, EM_DIA, GATILHO] as const;
export const TODOS = [ATRASADA, DADO_FALTANDO, VENCE_LOGO, EM_DIA, CUMPRIDA, GATILHO] as const;
export type Status = (typeof TODOS)[number];

export const ROTULO: Record<string, string> = {
  [ATRASADA]: "Atrasada",
  [DADO_FALTANDO]: "Cadastro incompleto",
  [VENCE_LOGO]: "Próximo ao vencimento",
  [EM_DIA]: "Em dia",
  [CUMPRIDA]: "Cumprida",
  [GATILHO]: "Por gatilho",
};

/** Cabeçalho curto das contagens nas tabelas. */
export const COLUNA: Record<string, string> = {
  [ATRASADA]: "Atrasadas",
  [DADO_FALTANDO]: "Falta dado",
  [VENCE_LOGO]: "Vencendo",
  [EM_DIA]: "Em dia",
  [GATILHO]: "Gatilho",
};

export const ORDEM: Record<string, number> = {
  [ATRASADA]: 0, [DADO_FALTANDO]: 1, [VENCE_LOGO]: 2, [EM_DIA]: 3, [CUMPRIDA]: 4, [GATILHO]: 5,
};

/** Classes de cor por status (strings inteiras para o Tailwind encontrar). */
export const COR: Record<string, { texto: string; fundo: string; borda: string; topo: string; esquerda: string; ponto: string; hex: string }> = {
  [ATRASADA]: { texto: "text-atrasada", fundo: "bg-atrasada-fundo", borda: "border-atrasada", topo: "border-t-atrasada", esquerda: "border-l-atrasada", ponto: "bg-atrasada", hex: "var(--atrasada)" },
  [DADO_FALTANDO]: { texto: "text-faltando", fundo: "bg-faltando-fundo", borda: "border-faltando", topo: "border-t-faltando", esquerda: "border-l-faltando", ponto: "bg-faltando", hex: "var(--faltando)" },
  [VENCE_LOGO]: { texto: "text-vence", fundo: "bg-vence-fundo", borda: "border-vence-marca", topo: "border-t-vence-marca", esquerda: "border-l-vence-marca", ponto: "bg-vence-marca", hex: "var(--vence-marca)" },
  [EM_DIA]: { texto: "text-emdia", fundo: "bg-emdia-fundo", borda: "border-emdia", topo: "border-t-emdia", esquerda: "border-l-emdia", ponto: "bg-emdia", hex: "var(--emdia)" },
  [CUMPRIDA]: { texto: "text-emdia", fundo: "bg-emdia-fundo", borda: "border-emdia", topo: "border-t-emdia", esquerda: "border-l-emdia", ponto: "bg-emdia", hex: "var(--emdia)" },
  [GATILHO]: { texto: "text-gatilho", fundo: "bg-gatilho-fundo", borda: "border-gatilho", topo: "border-t-gatilho", esquerda: "border-l-gatilho", ponto: "bg-gatilho", hex: "var(--gatilho)" },
};

export function cor(status: string) {
  return COR[status] ?? COR[EM_DIA]!;
}

/** Pior status de uma contagem: atrasada > dado faltando > vence em breve > em dia. */
export function pior(contagem: Record<string, number | undefined>): Status {
  for (const s of [ATRASADA, DADO_FALTANDO, VENCE_LOGO] as const) if ((contagem[s] ?? 0) > 0) return s;
  return EM_DIA;
}

/** Ordena como a torre: status, depois o vencimento mais próximo, depois o ativo. */
export function ordenar<T extends { status: string; vence?: string | null; ativo: string }>(linhas: T[]): T[] {
  return [...linhas].sort((a, b) =>
    (ORDEM[a.status] ?? 9) - (ORDEM[b.status] ?? 9) ||
    (a.vence ?? "9999").localeCompare(b.vence ?? "9999") ||
    a.ativo.localeCompare(b.ativo));
}

export const TIPO_ATIVO: Record<string, string> = {
  barragem: "Barragem", unidade: "Unidade de mineração", equipamento: "Equipamento", licenca: "Licença ambiental",
};

/** Quem cobra a norma (pelo nome dela): ANM, MTE (NR) ou órgão ambiental. */
export function orgao(norma: string): string {
  if (norma.includes("ANM")) return "ANM";
  if (norma.startsWith("NR-")) return "MTE";
  if (norma.startsWith("LO ") || norma.startsWith("LC 140")) return "Órgão ambiental";
  if (norma.startsWith("Lei ")) return "Lei federal";
  return "—";
}
