"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { FiltroMulti } from "@/components/filtro";
import { CampoEntrada, CampoSelecao, Carregando, ErroCarga, Etiqueta, Titulo, Vazio } from "@/components/ui";
import { api, dados, type Esquemas } from "@/lib/api";
import { curto, emBrasilia, plural } from "@/lib/formato";
import { useTorre } from "@/lib/torre";

type Linha = Esquemas["Linha"];
const LIMITES = [200, 500, 1000];

function detalhe(d: Linha["detalhe"]): string {
  if (d === null || d === undefined) return "";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(String).join(", ");
  return Object.entries(d).map(([k, v]) => `${k}: ${typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)}`).join(" · ");
}

export default function Auditoria() {
  const t = useTorre();
  const [limite, setLimite] = useState(200);
  const [acoes, setAcoes] = useState<string[]>([]);
  const [busca, setBusca] = useState("");
  const trilha = useQuery({
    queryKey: ["auditoria", t.eu.visao, limite],
    queryFn: () => dados(api.GET("/api/v1/auditoria", { params: { query: { limite } } })),
  });
  const todas = useMemo(() => trilha.data ?? [], [trilha.data]);
  const opcoes = [...new Set(todas.map((l) => l.acao))].sort().map((a) => ({ valor: a, rotulo: a.replace(/_/g, " ") }));
  const termo = busca.trim().toLowerCase();
  const linhas = todas.filter((l) => (!acoes.length || acoes.includes(l.acao))
    && (!termo || `${l.em} ${emBrasilia(l.em)} ${l.usuario} ${l.alvo} ${detalhe(l.detalhe)}`.toLowerCase().includes(termo)));

  return (
    <>
      <Titulo titulo="Auditoria" />
      <div className="grid gap-3 sm:grid-cols-[1fr_2fr_160px]">
        <FiltroMulti rotulo="Ação" valor={acoes} onMudar={setAcoes} opcoes={opcoes} todos="todas" />
        <CampoEntrada rotulo="Buscar" type="search" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="data, e-mail, nome do usuário, ativo, obrigação…" />
        <CampoSelecao rotulo="Últimas" value={limite} onChange={(e) => setLimite(Number(e.target.value))}>
          {LIMITES.map((n) => <option key={n} value={n}>{n} ações</option>)}
        </CampoSelecao>
      </div>
      {trilha.isLoading && <Carregando linhas={8} className="mt-4" />}
      {trilha.error && <div className="mt-4"><ErroCarga erro={trilha.error} onTentar={() => trilha.refetch()} /></div>}
      {trilha.data && (
        <>
          <p className="mt-4 text-xs text-texto-2">{linhas.length} de {plural(todas.length, "ação", "ações")}</p>
          <div className="mt-2 max-h-[640px] overflow-auto rounded-lg border border-borda">
            <table className="w-full min-w-[900px] text-sm" data-testid="auditoria">
              <thead className="sticky top-0 bg-fundo-2 text-left text-xs text-texto-2">
                <tr>{["Data", "E-mail", "Ação", "Nome do Usuário", "Detalhe", "Resultado", ...(t.plataforma ? ["Empresa"] : [])].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-borda">
                {linhas.map((l) => (
                  <tr key={l.id}>
                    <td className="num px-3 py-2 whitespace-nowrap text-texto-2">{emBrasilia(l.em)}</td>
                    <td className="px-3 py-2">{l.usuario ?? "—"}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{l.acao.replace(/_/g, " ")}</td>
                    <td className="px-3 py-2">{l.alvo ?? "—"}</td>
                    <td className="px-3 py-2 text-texto-2" title={detalhe(l.detalhe)}>{curto(detalhe(l.detalhe), 90)}</td>
                    <td className="px-3 py-2">{l.resultado === "ok" ? <Etiqueta tom="ok">ok</Etiqueta> : <Etiqueta tom="perigo">{l.resultado}</Etiqueta>}</td>
                    {t.plataforma && <td className="px-3 py-2 text-texto-2">{l.empresa ?? "—"}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
            {!linhas.length && <div className="p-4"><Vazio>Nenhuma ação com esses filtros.</Vazio></div>}
          </div>
        </>
      )}
    </>
  );
}
