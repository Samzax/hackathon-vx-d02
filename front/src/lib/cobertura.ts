// A cobertura normativa na tela. Coberta é verde, mas sempre com as lacunas conhecidas ao lado; triagem,
// curadoria ou extração pendente é amarelo; sem fonte automática (ou fonte ainda não lida) é cinza com
// "cobertura não verificada". O que não foi verificado nunca sai verde, nem se a API mandar um estado novo.
import { emBrasilia, numero } from "./formato";

export type TomCobertura = "verde" | "amarelo" | "cinza";

export const PENDENTES = ["triagem_pendente", "curadoria_pendente", "extracao_pendente"] as const;

export function tomDaCobertura(estado: string, verificada: boolean): TomCobertura {
  if (!verificada) return "cinza";
  if (estado === "coberta") return "verde";
  if ((PENDENTES as readonly string[]).includes(estado)) return "amarelo";
  return "cinza";
}

/** Classes inteiras (para o Tailwind encontrar) e o tom da etiqueta de cada cor. */
export const CLASSES: Record<TomCobertura, { etiqueta: "ok" | "atencao" | "neutro"; esquerda: string; ponto: string }> = {
  verde: { etiqueta: "ok", esquerda: "border-l-emdia", ponto: "bg-emdia" },
  amarelo: { etiqueta: "atencao", esquerda: "border-l-vence-marca", ponto: "bg-vence-marca" },
  cinza: { etiqueta: "neutro", esquerda: "border-l-borda-forte", ponto: "bg-texto-3" },
};

/** O texto da etiqueta: o rótulo da API; sem verificação, sempre com "cobertura não verificada". */
export function rotuloDaCobertura(estadoRotulo: string, verificada: boolean): string {
  if (verificada || /cobertura não verificada/i.test(estadoRotulo)) return estadoRotulo;
  return `${estadoRotulo}: cobertura não verificada`;
}

type Fonte = { nome: string; desde: number; ate: number; em: string };

/** "Assembleia de Minas, 1989–2026, lida em 06/11/2026" (a data em Brasília). */
export function fonteLida(f: Fonte): string {
  const anos = f.desde === f.ate ? String(f.desde) : `${f.desde}–${f.ate}`;
  return `${f.nome}, ${anos}, lida em ${emBrasilia(f.em, false)}`;
}

/** 0.96 -> "0,96" */
export function confianca(c: number): string {
  return numero(c, 2);
}
