"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Esquemas } from "@/lib/api";
import { curto, dataBR, diasEntre, MESES, plural } from "@/lib/formato";

type Faixa = Esquemas["Faixa"];
type Futura = Esquemas["Futura"];

const INICIO_ANTIGO = "1900-01-01";
const SEM_FIM = "2999-12-31";
const ROTULO = 200; // coluna dos nomes das linhas
const LINHA = 28;
const TOPO = 30;
const BASE = 26;

function curta(n: string): string {
  return n.replace("Res. ANM ", "ANM ").replace(" (fictícia)", "");
}

function useLargura<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [largura, setLargura] = useState(900);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new ResizeObserver(([e]) => setLargura(Math.max(560, Math.round(e!.contentRect.width))));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, largura };
}

/**
 * Linha do tempo da vigência: uma barra por norma que vale para cada ativo, de hoje até o horizonte;
 * losangos nos dias em que obrigações passam a valer (vazado laranja = data de uma mudança ainda não
 * aprovada). Clicar num losango escolhe o dia.
 */
export function Gantt({ faixas, futuras, hoje, horizonte, marcos, ordemAtivos, dia, onDia }: {
  faixas: Faixa[]; futuras: Futura[]; hoje: string; horizonte: string; marcos: { dia: string; rotulo: string }[];
  ordemAtivos: string[]; dia: string | null; onDia: (dia: string) => void;
}) {
  const { ref, largura } = useLargura<HTMLDivElement>();

  const { linhas, normas } = useMemo(() => {
    const visiveis = faixas.filter((f) => (f.desde ?? INICIO_ANTIGO) <= horizonte && (f.ate ?? SEM_FIM) >= hoje);
    const pos = new Map(ordemAtivos.map((a, i) => [a, i]));
    // a ANM primeiro dentro de cada ativo
    const ordem = [...visiveis].sort((a, b) => (pos.get(a.ativo) ?? 99) - (pos.get(b.ativo) ?? 99)
      || Number(!a.norma.includes("ANM")) - Number(!b.norma.includes("ANM")) || a.norma.localeCompare(b.norma));
    const ns = [...new Set(faixas.map((f) => f.norma))].sort((a, b) => Number(!a.includes("ANM")) - Number(!b.includes("ANM")) || a.localeCompare(b));
    return { linhas: ordem, normas: ns };
  }, [faixas, hoje, horizonte, ordemAtivos]);

  const pontos = useMemo(() => {
    const g = new Map<string, Futura[]>();
    for (const f of futuras) {
      if (f.dia > horizonte) continue;
      const k = `${f.ativo}|${f.norma ?? "—"}|${f.dia}`;
      g.set(k, [...(g.get(k) ?? []), f]);
    }
    return [...g.entries()].map(([k, fs]) => {
      const [ativo, norma, d] = k.split("|") as [string, string, string];
      return { ativo, norma, dia: d, fs, proposta: fs.some((f) => f.proposta) };
    });
  }, [futuras, horizonte]);

  const total = Math.max(1, diasEntre(hoje, horizonte));
  const area = largura - ROTULO - 12;
  const x = (d: string) => ROTULO + (Math.min(Math.max(diasEntre(hoje, d), 0), total) / total) * area;
  const altura = TOPO + linhas.length * LINHA + BASE;
  const indice = new Map(linhas.map((l, i) => [`${l.ativo}|${l.norma}`, i]));
  const cor = (n: string) => `var(--serie-${(normas.indexOf(n) % 8) + 1})`;

  // marcas do eixo: janeiro e julho de cada ano no intervalo
  const ticks: string[] = [];
  for (let a = Number(hoje.slice(0, 4)); a <= Number(horizonte.slice(0, 4)); a++) {
    for (const m of ["01", "07"]) {
      const d = `${a}-${m}-01`;
      if (d > hoje && d <= horizonte) ticks.push(d);
    }
  }

  return (
    <div ref={ref} className="w-full">
      {linhas.length > 0 && <>
      <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-texto-2" aria-label="Legenda">
        {normas.filter((n) => linhas.some((l) => l.norma === n)).map((n) => (
          <li key={n} className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-sm" style={{ background: cor(n) }} aria-hidden />{n}</li>
        ))}
        <li className="flex items-center gap-1.5">
          <svg width="12" height="12" aria-hidden><path d="M6 1 L11 6 L6 11 L1 6 Z" fill="var(--texto)" /></svg>obrigações passam a valer
        </li>
        <li className="flex items-center gap-1.5">
          <svg width="12" height="12" aria-hidden><path d="M6 1.5 L10.5 6 L6 10.5 L1.5 6 Z" fill="var(--fundo)" stroke="var(--proposta)" strokeWidth="2" /></svg>data de mudança ainda não aprovada
        </li>
      </ul>
      <div className="w-full overflow-x-auto">
        <svg width={largura} height={altura} role="img" aria-label="Linha do tempo da vigência das normas por ativo" className="text-texto">
          {/* grade e eixo */}
          {ticks.map((d) => (
            <g key={d}>
              <line x1={x(d)} x2={x(d)} y1={TOPO - 6} y2={altura - BASE} stroke="var(--borda)" />
              <text x={x(d)} y={altura - 8} textAnchor="middle" fontSize="11" fill="var(--texto-3)">{MESES[Number(d.slice(5, 7)) - 1]!.slice(0, 3)}/{d.slice(0, 4)}</text>
            </g>
          ))}
          {marcos.filter((m) => m.dia >= hoje && m.dia <= horizonte).map((m, i) => (
            <g key={m.rotulo}>
              <line x1={x(m.dia)} x2={x(m.dia)} y1={TOPO - 8} y2={altura - BASE} stroke="var(--texto-3)" strokeDasharray="4 3" />
              <text x={x(m.dia) + 4} y={TOPO - 12 - (i % 2) * 0} fontSize="11" fill="var(--texto-2)">{m.rotulo}</text>
            </g>
          ))}
          {/* linhas: ativo · norma */}
          {linhas.map((l, i) => {
            const y = TOPO + i * LINHA;
            const ini = (l.desde ?? INICIO_ANTIGO) > hoje ? l.desde! : hoje;
            const fim = (l.ate ?? SEM_FIM) < horizonte ? l.ate! : horizonte;
            const vale = `${l.desde ? dataBR(l.desde) : "antes da demo"} até ${l.ate ? dataBR(l.ate) : "sem data de fim"}`;
            return (
              <g key={`${l.ativo}|${l.norma}`}>
                <text x={0} y={y + LINHA / 2 + 4} fontSize="12" fill="var(--texto)">
                  <tspan fontWeight="600">{l.ativo}</tspan><tspan fill="var(--texto-2)"> · {curto(curta(l.norma), 24)}</tspan>
                </text>
                <rect x={x(ini)} y={y + LINHA / 2 - 5} width={Math.max(2, x(fim) - x(ini))} height={10} rx={4} fill={cor(l.norma)} opacity={0.9}>
                  <title>{`${l.ativo} · ${l.norma}: vale ${vale}`}</title>
                </rect>
              </g>
            );
          })}
          {/* losangos: dias em que obrigações passam a valer */}
          {pontos.map((p) => {
            const i = indice.get(`${p.ativo}|${p.norma}`);
            if (i === undefined) return null;
            const cx = x(p.dia);
            const cy = TOPO + i * LINHA + LINHA / 2;
            const r = 7;
            const escolhido = dia === p.dia;
            const quais = p.fs.slice(0, 3).map((f) => curto(f.titulo, 50)).join("; ") + (p.fs.length > 3 ? ` e mais ${p.fs.length - 3}` : "");
            return (
              <g key={`${p.ativo}|${p.norma}|${p.dia}`} role="button" tabIndex={0} className="cursor-pointer"
                aria-label={`${dataBR(p.dia)}: ${plural(p.fs.length, "obrigação passa", "obrigações passam")} a valer em ${p.ativo}`}
                onClick={() => onDia(p.dia)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onDia(p.dia); } }}>
                <rect x={cx - 12} y={cy - 12} width={24} height={24} fill="transparent" />
                <path d={`M${cx} ${cy - r} L${cx + r} ${cy} L${cx} ${cy + r} L${cx - r} ${cy} Z`}
                  fill={p.proposta ? "var(--fundo)" : "var(--texto)"} stroke={p.proposta ? "var(--proposta)" : "var(--fundo)"}
                  strokeWidth={p.proposta ? 2.5 : 2} />
                {escolhido && <circle cx={cx} cy={cy} r={11} fill="none" stroke="var(--marca)" strokeWidth={2} />}
                <title>{`${p.ativo} · ${p.norma} · ${dataBR(p.dia)}: ${plural(p.fs.length, "obrigação", "obrigações")} (${quais})${p.proposta ? " · data proposta, ainda não aprovada" : ""}`}</title>
              </g>
            );
          })}
        </svg>
      </div>
      </>}
    </div>
  );
}
