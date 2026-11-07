"use client";

import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useMemo, useState } from "react";
import { api, dados, type Esquemas } from "@/lib/api";
import { DIAS_SEMANA, MESES, curto, dataBR, mesesAoRedor, plural, semanasDoMes } from "@/lib/formato";
import { useEmpresa, useTorre } from "@/lib/torre";
import { type AlvoEntrega, DialogoEntrega } from "./entrega";
import { Carregando, Cartao, ErroCarga, Etiqueta, Expansivel, Selecao, cx, Botao } from "./ui";

type Vencimento = Esquemas["Vencimento"];
type Situacao = "ok" | "atraso" | "vence";

const SITUACAO: Record<Situacao, { rotulo: string; tom: "ok" | "perigo" | "atencao"; celula: string }> = {
  atraso: { rotulo: "venceu sem entrega", tom: "perigo", celula: "bg-atrasada-fundo text-atrasada" },
  vence: { rotulo: "a vencer", tom: "atencao", celula: "bg-vence-fundo text-vence" },
  ok: { rotulo: "entregue", tom: "ok", celula: "bg-emdia-fundo text-emdia" },
};

/** Os vencimentos do mês num calendário: cada dia com a cor do pior vencimento; clicar mostra a lista. */
export function Calendario({ ativos }: { ativos: string[] }) {
  const t = useTorre();
  const empresa = useEmpresa();
  const meses = useMemo(() => mesesAoRedor(t.hoje, 1, 11), [t.hoje]);
  const [mes, setMes] = useState(meses[1]!);
  const [dia, setDia] = useState<string | null>(null);
  const [alvo, setAlvo] = useState<AlvoEntrega | null>(null);
  const ano = Number(mes.slice(0, 4));
  const m = Number(mes.slice(5, 7));
  const venc = useQuery({
    queryKey: [...t.chave, "calendario", mes, ativos],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/calendario", {
      params: { path: { empresa_id: empresa.id }, query: { ano, mes: m, hoje: t.hoje, ativo: ativos.length ? ativos : undefined } },
    })),
  });
  const situacao = (x: Vencimento): Situacao => (x.entregue ? "ok" : x.dia < t.hoje ? "atraso" : "vence");
  const porDia = useMemo(() => {
    const p = new Map<number, Vencimento[]>();
    for (const x of venc.data ?? []) {
      const d = Number(x.dia.slice(8, 10));
      p.set(d, [...(p.get(d) ?? []), x]);
    }
    return p;
  }, [venc.data]);
  const semanas = semanasDoMes(ano, m);
  const iso = (d: number) => `${mes.slice(0, 8)}${String(d).padStart(2, "0")}`;
  const doDia = dia && dia.slice(0, 7) === mes.slice(0, 7) ? porDia.get(Number(dia.slice(8, 10))) ?? [] : null;

  return (
    <div data-testid="calendario">
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-[13px] font-medium text-texto-2">Mês</span>
          <Selecao value={mes} onChange={(e) => { setMes(e.target.value); setDia(null); }} className="w-48">
            {meses.map((x) => <option key={x} value={x}>{MESES[Number(x.slice(5, 7)) - 1]}/{x.slice(0, 4)}</option>)}
          </Selecao>
        </label>
        <p className="pb-2 text-xs text-texto-2">
          {venc.data ? plural(venc.data.length, "vencimento", "vencimentos") : "…"} em {MESES[m - 1]}/{ano} ·{" "}
          <span className="font-semibold text-atrasada">vermelho</span>: venceu sem entrega ·{" "}
          <span className="font-semibold text-vence">amarelo</span>: a vencer · <span className="font-semibold text-emdia">verde</span>: entregue.
          {ativos.length > 0 && " O filtro de ativo acima vale aqui."}
        </p>
      </div>
      {venc.error && <ErroCarga erro={venc.error} onTentar={() => venc.refetch()} />}
      {venc.isLoading ? <Carregando linhas={5} /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] table-fixed border-separate border-spacing-1 text-sm">
            <thead>
              <tr>{DIAS_SEMANA.map((d) => <th key={d} className="pb-1 text-xs font-medium text-texto-3">{d}</th>)}</tr>
            </thead>
            <tbody>
              {semanas.map((s, i) => (
                <tr key={i}>
                  {s.map((d, j) => {
                    if (!d) return <td key={j} />;
                    const xs = porDia.get(d) ?? [];
                    const sits = new Set(xs.map(situacao));
                    const pior: Situacao | null = sits.has("atraso") ? "atraso" : sits.has("vence") ? "vence" : xs.length ? "ok" : null;
                    const hoje = iso(d) === t.hoje;
                    return (
                      <td key={j}>
                        <button type="button" onClick={() => setDia(iso(d))} aria-pressed={dia === iso(d)}
                          aria-label={`${dataBR(iso(d))}: ${plural(xs.length, "vencimento", "vencimentos")}`}
                          className={cx("flex h-14 w-full flex-col items-start rounded-md border px-2 py-1 text-left",
                            pior ? cx(SITUACAO[pior].celula, "border-transparent font-semibold") : "border-borda hover:bg-fundo-2",
                            dia === iso(d) && "ring-2 ring-marca", hoje && "outline-2 outline-marca")}>
                          <span className={cx("num text-xs", hoje && "font-bold text-marca")}>{d}{hoje && " · hoje"}</span>
                          {xs.length > 0 && <span className="num mt-auto text-[11px]">{xs.length} venc.</span>}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {doDia ? (
        <Cartao className="mt-3 px-4 py-3">
          <p className="text-sm font-semibold">{dataBR(dia)} · {plural(doDia.length, "vencimento", "vencimentos")}</p>
          <ul className="divide-y divide-borda">
            {doDia.map((x) => {
              const s = SITUACAO[situacao(x)];
              return (
                <li key={`${x.ativo}-${x.codigo}-${x.periodo}`} className="flex flex-col gap-2 py-2.5 sm:flex-row sm:items-center">
                  <div className="min-w-0 flex-1 text-sm">
                    <p><Etiqueta tom={s.tom}>{s.rotulo}</Etiqueta> <strong>{x.ativo}</strong> · {curto(x.titulo, 80)}</p>
                    <p className="text-xs text-texto-2">{x.periodo_rotulo} · {x.responsavel ?? "sem responsável"}</p>
                  </div>
                  {!x.entregue && x.ativo_id && !t.soLeitura && (
                    <Botao tamanho="p" icone={<Check className="size-3.5" />}
                      onClick={() => setAlvo({ ativo_id: x.ativo_id, ativo: x.ativo, codigo: x.codigo, titulo: x.titulo, status: x.status })}>
                      Registrar entrega
                    </Botao>
                  )}
                </li>
              );
            })}
          </ul>
          {!doDia.length && <p className="py-2 text-sm text-texto-2">Nenhum vencimento neste dia.</p>}
        </Cartao>
      ) : <p className="mt-2 text-xs text-texto-3">Clique num dia para ver os vencimentos{t.soLeitura ? "" : " e registrar a entrega"}.</p>}

      {!!venc.data?.length && (
        <Expansivel className="mt-3" resumo={<span className="font-medium">Lista dos {venc.data.length} vencimentos de {MESES[m - 1]}/{ano}</span>}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-xs text-texto-2">
                <tr>{["Dia", "Ativo", "Obrigação", "Período", "Situação", "Responsável"].map((h) => <th key={h} className="px-2 py-1.5 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-borda">
                {venc.data.map((x) => (
                  <tr key={`${x.ativo}-${x.codigo}-${x.periodo}`}>
                    <td className="num px-2 py-1.5">{dataBR(x.dia)}</td>
                    <td className="px-2 py-1.5">{x.ativo}</td>
                    <td className="px-2 py-1.5">{x.titulo}</td>
                    <td className="px-2 py-1.5 text-texto-2">{x.periodo_rotulo}</td>
                    <td className="px-2 py-1.5">{SITUACAO[situacao(x)].rotulo}</td>
                    <td className="px-2 py-1.5 text-texto-2">{x.responsavel ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Expansivel>
      )}
      <DialogoEntrega alvo={alvo} onFechar={() => setAlvo(null)} />
    </div>
  );
}
