// Formatação para a tela, em português do Brasil. Nada aqui inventa dado: só muda a forma.

/** "2026-11-07" -> "07/11/2026"; vazio -> "—". Aceita "2026-11-07 13:00:00" (usa só a data). */
export function dataBR(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** "2026-11-07" -> "nov/2026" */
export function mesAno(iso: string): string {
  const [a, m] = iso.split("-");
  return `${MESES_CURTOS[Number(m) - 1]}/${a}`;
}

export const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
  "setembro", "outubro", "novembro", "dezembro"];
const MESES_CURTOS = MESES.map((m) => m.slice(0, 3));
export const DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"];

/**
 * O banco grava em UTC ("2026-11-05 16:53:43"); a tela mostra o horário de Brasília (UTC-3 o ano
 * todo desde 2019, sem horário de verão). Perto da meia-noite a data muda junto.
 */
export function emBrasilia(utc: string | null | undefined, comHora = true): string {
  if (!utc) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(utc);
  if (!m) return dataBR(utc);
  const t = new Date(Date.UTC(+m[1]!, +m[2]! - 1, +m[3]!, +m[4]! - 3, +m[5]!));
  const d = `${p2(t.getUTCDate())}/${p2(t.getUTCMonth() + 1)}/${t.getUTCFullYear()}`;
  return comHora ? `${d} ${p2(t.getUTCHours())}:${p2(t.getUTCMinutes())}` : d;
}

function p2(n: number): string {
  return String(n).padStart(2, "0");
}

/** 1234.5 -> "1.234,5" (casas fixas). */
export function numero(v: number, casas = 0): string {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** Número do cadastro: até 2 casas, sem ",00" sobrando (68 -> "68"; 9771474.42 -> "9.771.474,42"). */
export function numeroLivre(v: number): string {
  return v.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

/** 0.00231645 -> "US$ 0,0023" */
export function usd(v: number, casas = 4): string {
  return `US$ ${numero(v, casas)}`;
}

/** 1.5e6 -> "R$ 1,5 mi" */
export function reaisMilhoes(v: number): string {
  return `R$ ${numero(v / 1e6, 1)} mi`;
}

export function plural(n: number, singular: string, pluralForma: string): string {
  return `${numero(n)} ${n === 1 ? singular : pluralForma}`;
}

/** Corta no limite de palavra e marca com reticências. */
export function curto(texto: string, n = 70): string {
  if (texto.length <= n) return texto;
  const corte = texto.slice(0, n);
  const espaco = corte.lastIndexOf(" ");
  return (espaco > n * 0.5 ? corte.slice(0, espaco) : corte) + "…";
}

export function maiuscula(texto: string): string {
  return texto ? texto[0]!.toUpperCase() + texto.slice(1) : texto;
}

// ------------------------------------------------------------------ datas ISO (sem fuso: dia civil)

function paraData(iso: string): Date {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(a!, m! - 1, d!));
}

function deData(d: Date): string {
  return `${d.getUTCFullYear()}-${p2(d.getUTCMonth() + 1)}-${p2(d.getUTCDate())}`;
}

export function somarDias(iso: string, dias: number): string {
  const d = paraData(iso);
  d.setUTCDate(d.getUTCDate() + dias);
  return deData(d);
}

/** Dias de `de` até `ate` (negativo se `ate` vem antes). */
export function diasEntre(de: string, ate: string): number {
  return Math.round((paraData(ate).getTime() - paraData(de).getTime()) / 86_400_000);
}

export function ehDataISO(v: unknown): v is string {
  return typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
}

/** Primeiro dia de cada mês, de `antes` meses antes a `depois` meses depois de `iso`. */
export function mesesAoRedor(iso: string, antes = 1, depois = 11): string[] {
  const [a, m] = iso.split("-").map(Number);
  const out: string[] = [];
  for (let i = -antes; i <= depois; i++) {
    const t = new Date(Date.UTC(a!, m! - 1 + i, 1));
    out.push(deData(t));
  }
  return out;
}

/** As semanas do mês, de segunda a domingo; 0 onde o dia é de outro mês. */
export function semanasDoMes(ano: number, mes: number): number[][] {
  const primeiro = new Date(Date.UTC(ano, mes - 1, 1));
  const dias = new Date(Date.UTC(ano, mes, 0)).getUTCDate();
  const recuo = (primeiro.getUTCDay() + 6) % 7; // segunda = 0
  const celulas = [...Array(recuo).fill(0), ...Array.from({ length: dias }, (_, i) => i + 1)];
  while (celulas.length % 7) celulas.push(0);
  const out: number[][] = [];
  for (let i = 0; i < celulas.length; i += 7) out.push(celulas.slice(i, i + 7));
  return out;
}

/** Nome de arquivo seguro: "Gerência de Geotecnia" -> "Gerencia_de_Geotecnia". */
export function nomeDeArquivo(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_|_$/g, "");
}
