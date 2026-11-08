"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, CheckCheck, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { useAvisar } from "@/components/avisos";
import {
  Aviso, Botao, Carregando, Cartao, CampoSelecao, Entrada, ErroCarga, Etiqueta, Expansivel, Secao, Titulo, Vazio, mensagem,
} from "@/components/ui";
import { api, dados, type Esquemas } from "@/lib/api";
import { type Mudanca, useInvalidarTorre, useMudancas } from "@/lib/consultas";
import { curto, dataBR, emBrasilia, usd } from "@/lib/formato";
import { useEmpresa, useTorre } from "@/lib/torre";
import { LinkOficial } from "@/components/link-oficial";

type Versao = Esquemas["VersaoObrigacao"];

const SITUACAO_VERSAO: Record<string, { rotulo: string; tom: "ok" | "neutro" | "proposta" | "perigo" }> = {
  vigente: { rotulo: "vigente", tom: "ok" },
  substituida: { rotulo: "substituída", tom: "neutro" },
  pendente: { rotulo: "pendente", tom: "proposta" },
  rejeitada: { rotulo: "rejeitada", tom: "perigo" },
};

function useDecidir() {
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  return useMutation({
    mutationFn: ({ m, aprovar, correcoes }: { m: Mudanca; aprovar: boolean; correcoes?: Record<string, string | null> }) =>
      dados(api.POST("/api/v1/mudancas/{versao_id}/decisao", { params: { path: { versao_id: m.versao_id } }, body: { aprovar, correcoes: correcoes ?? null } })),
    onSuccess: (_, v) => {
      avisar(`${v.m.codigo}: mudança ${v.aprovar ? (v.correcoes ? "aprovada com correção" : "aprovada") : "rejeitada"}. Fica registrado quem decidiu.`);
      invalidar();
    },
    onError: (e) => avisar(`Decisão não aceita: ${mensagem(e)}`, "erro"),
  });
}

function CartaoMudanca({ m }: { m: Mudanca }) {
  const decidir = useDecidir();
  const [correcoes, setCorrecoes] = useState<Record<string, string>>(() => Object.fromEntries(m.campos.map((c) => [c.campo, c.proposto ?? ""])));
  const corrigiu = m.campos.some((c) => (correcoes[c.campo] ?? "") !== (c.proposto ?? ""));
  const a = m.analise;

  return (
    <Cartao className="p-4 sm:p-5" id={`m${m.versao_id}`} data-testid="mudanca">
      <div className="flex flex-wrap items-center gap-2">
        <Etiqueta tom="proposta">aguardando decisão</Etiqueta>
        <Etiqueta tom="neutro">{m.escopo}</Etiqueta>
      </div>
      <h2 className="mt-2 text-base font-semibold">{m.codigo} · {m.titulo}</h2>
      <p className="mt-0.5 text-[13px] text-texto-2">
        Origem: <LinkOficial href={m.ato_link}>{m.ato ?? m.fonte}</LinkOficial> · publicado no DOU em {dataBR(m.publicado_em)}
        {m.norma && <> · <LinkOficial href={m.norma_link}>{m.norma}</LinkOficial></>}
      </p>

      <div className="mt-4 overflow-x-auto rounded-lg border border-borda">
        <table className="w-full text-sm">
          <thead className="bg-fundo-2 text-left text-xs text-texto-2">
            <tr><th className="px-3 py-2 font-medium">Campo</th><th className="px-3 py-2 font-medium">Hoje</th><th className="px-3 py-2 font-medium">Proposto</th></tr>
          </thead>
          <tbody className="divide-y divide-borda">
            {m.campos.map((c) => (
              <tr key={c.campo}>
                <td className="px-3 py-2">{c.rotulo}</td>
                <td className="num px-3 py-2 text-texto-2">{c.vigente_texto}</td>
                <td className="num px-3 py-2 font-semibold">{c.proposto_texto}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {m.trecho && (
        <figure className="mt-4">
          <figcaption className="mb-1 text-xs font-semibold uppercase tracking-wide text-texto-3">Trecho do ato</figcaption>
          <blockquote className="border-l-2 border-marca pl-3 text-sm italic">“{m.trecho}”</blockquote>
        </figure>
      )}

      {a && (
        <div className="mt-4 space-y-2 rounded-md bg-fundo-2 px-4 py-3 text-[13px]">
          <p><span className="font-semibold">Por quê:</span> {a.motivo}</p>
          {m.conferencia.length > 0 && (
            <div>
              <p className="flex items-center gap-1.5 font-semibold"><ShieldCheck className="size-4 text-emdia" aria-hidden />Conferência automática</p>
              <ul className="mt-1 space-y-0.5">
                {m.conferencia.map((c) => <li key={c} className="flex gap-1.5"><Check className="mt-0.5 size-3.5 shrink-0 text-emdia" aria-hidden />{c}</li>)}
              </ul>
            </div>
          )}
          <p className="text-texto-2">Custo da análise {usd(a.custo_original_usd)}{a.confianca !== null ? ` · confiança ${String(a.confianca).replace(".", ",")}` : ""}</p>
          {m.tamanho && <p className="font-medium">{m.tamanho}</p>}
        </div>
      )}
      <p className="mt-3 text-sm">Ativos afetados: <strong>{m.ativos.join(", ")}</strong></p>

      {m.decide ? (
        <>
          <div className="mt-4 flex flex-wrap gap-2">
            <Botao variante="primario" icone={<Check className="size-4" />} carregando={decidir.isPending && decidir.variables?.aprovar && !decidir.variables.correcoes}
              disabled={decidir.isPending} onClick={() => decidir.mutate({ m, aprovar: true })}>
              Aprovar
            </Botao>
            <Botao variante="perigo" icone={<X className="size-4" />} disabled={decidir.isPending} onClick={() => decidir.mutate({ m, aprovar: false })}>
              Rejeitar
            </Botao>
          </div>
          <Expansivel className="mt-3" resumo={<span className="font-medium">Corrigir e aprovar</span>}>
            <p className="mb-3 text-[13px] text-texto-2">
              Se a proposta errou um valor, corrija aqui. Fica registrado o que foi proposto, o que foi aprovado e por quem.
            </p>
            <form className="space-y-3" onSubmit={(e) => {
              e.preventDefault();
              decidir.mutate({ m, aprovar: true, correcoes: Object.fromEntries(m.campos.map((c) => [c.campo, correcoes[c.campo] || null])) });
            }}>
              <div className="grid gap-3 sm:grid-cols-2">
                {m.campos.map((c) => (
                  <label key={c.campo} className="flex flex-col gap-1">
                    <span className="text-[13px] font-medium text-texto-2">{c.rotulo}</span>
                    <Entrada type={c.data ? "date" : "text"} value={correcoes[c.campo] ?? ""} onChange={(e) => setCorrecoes((x) => ({ ...x, [c.campo]: e.target.value }))} />
                  </label>
                ))}
              </div>
              <Botao type="submit" disabled={!corrigiu || decidir.isPending} carregando={decidir.isPending && !!decidir.variables?.correcoes}>
                Aprovar com correção
              </Botao>
            </form>
          </Expansivel>
        </>
      ) : (
        <Aviso tipo="info" className="mt-4">
          Quem decide esta mudança: <strong>{m.quem_decide}</strong>.
          {m.escopo === "norma pública" && " É norma pública: vale para todas as clientes, por isso a curadoria da Mitra aprova uma vez para todas."}
          {" "}Até lá, nada muda na torre.
        </Aviso>
      )}
    </Cartao>
  );
}

function Decisoes() {
  const t = useTorre();
  const empresa = useEmpresa();
  const d = useQuery({
    queryKey: [...t.chave, "decisoes"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/decisoes", { params: { path: { empresa_id: empresa.id } } })),
  });
  if (d.isLoading) return <Carregando linhas={2} />;
  if (d.error) return <ErroCarga erro={d.error} onTentar={() => d.refetch()} />;
  if (!d.data?.length) return <Vazio>Nenhuma decisão registrada ainda.</Vazio>;
  return (
    <div className="overflow-x-auto rounded-lg border border-borda">
      <table className="w-full min-w-[640px] text-sm" data-testid="decisoes">
        <thead className="bg-fundo-2 text-left text-xs text-texto-2">
          <tr>{["Obrigação", "Ato", "Decisão", "Por", "Quando (Brasília)"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-borda">
          {d.data.map((x) => (
            <tr key={x.versao_id}>
              <td className="px-3 py-2 font-medium">{x.codigo}</td>
              <td className="px-3 py-2"><LinkOficial href={x.ato_link}>{x.ato_nome ?? "—"}</LinkOficial></td>
              <td className="px-3 py-2">
                {!x.aprovada ? <Etiqueta tom="perigo">rejeitada</Etiqueta> : x.corrigida ? <Etiqueta tom="proposta">aprovada com correção</Etiqueta> : <Etiqueta tom="ok">aprovada</Etiqueta>}
              </td>
              <td className="px-3 py-2 text-texto-2">{(x.decidida_por ?? "—").split(" (")[0]}</td>
              <td className="num px-3 py-2 text-texto-2">{emBrasilia(x.decidida_em)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Versao({ v }: { v: Versao }) {
  const s = SITUACAO_VERSAO[v.status] ?? { rotulo: v.status, tom: "neutro" as const };
  const quem = (v.decidida_por ?? "").split(" (")[0];
  const quando = emBrasilia(v.decidida_em, false);
  return (
    <li className="border-l-2 border-borda-forte py-1 pl-4">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <strong>Versão {v.versao}</strong>
        <Etiqueta tom={s.tom}>{s.rotulo}</Etiqueta>
        <span className="text-texto-2">
          origem: <LinkOficial href={v.ato_link}>{v.ato_nome ?? v.fonte ?? "cadastro inicial"}</LinkOficial>
          {quem && (quem === "carga inicial" ? ` · veio do cadastro inicial em ${quando}` : ` · decidida por ${quem} em ${quando}`)}
        </span>
      </p>
      {v.mudou.length > 0 ? (
        <p className="mt-1 text-sm">
          {v.mudou.map((c, i) => <span key={c.campo}>{i > 0 && "; "}{c.rotulo}: {c.antes} → <strong>{c.depois}</strong></span>)}
        </p>
      ) : (
        <p className="mt-1 text-sm">
          Prazo: {dataBR(v.prazo)} · {v.vigencia_ate ? `vale de ${dataBR(v.vigencia_desde)} até ${dataBR(v.vigencia_ate)}` : `vale a partir de ${dataBR(v.vigencia_desde)}`} · <LinkOficial href={v.norma_link}>{v.dispositivo}</LinkOficial>
        </p>
      )}
      {v.corrigido.length > 0 && (
        <p className="mt-1 text-sm text-proposta">
          Corrigida por quem aprovou: {v.corrigido.map((c) => `${c.rotulo} proposto ${c.antes}, aprovado ${c.depois}`).join("; ")}
        </p>
      )}
      {v.trecho && <blockquote className="mt-1 text-[13px] italic text-texto-2">“{v.trecho}”</blockquote>}
    </li>
  );
}

function HistoricoDeObrigacao() {
  const t = useTorre();
  const empresa = useEmpresa();
  const lista = useQuery({
    queryKey: [...t.chave, "obrigacoes"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/obrigacoes", { params: { path: { empresa_id: empresa.id } } })),
  });
  const [codigo, setCodigo] = useState<string>("");
  const escolhido = codigo || lista.data?.[0]?.codigo || "";
  const h = useQuery({
    queryKey: ["historico-obrigacao", t.eu.visao, escolhido],
    queryFn: () => dados(api.GET("/api/v1/obrigacoes/{codigo}/historico", { params: { path: { codigo: escolhido } } })),
    enabled: !!escolhido,
  });
  if (lista.error) return <ErroCarga erro={lista.error} onTentar={() => lista.refetch()} />;
  return (
    <div className="space-y-4">
      <CampoSelecao rotulo="Obrigação" value={escolhido} onChange={(e) => setCodigo(e.target.value)} className="max-w-2xl">
        {(lista.data ?? []).map((o) => (
          <option key={o.codigo} value={o.codigo}>{o.codigo} · {curto(o.titulo, 90)}{o.mudou ? " (já mudou)" : ""}</option>
        ))}
      </CampoSelecao>
      {h.isLoading && <Carregando linhas={2} />}
      {h.error && <ErroCarga erro={h.error} onTentar={() => h.refetch()} />}
      {h.data && <ol className="space-y-4" data-testid="versoes">{h.data.map((v) => <Versao key={v.id} v={v} />)}</ol>}
    </div>
  );
}

export default function Mudancas() {
  const mudancas = useMudancas();
  return (
    <>
      <Titulo titulo="Mudanças">
        Mudanças propostas a partir de fontes oficiais
      </Titulo>
      {mudancas.isLoading && <Carregando linhas={4} />}
      {mudancas.error && <ErroCarga erro={mudancas.error} onTentar={() => mudancas.refetch()} />}
      {mudancas.data && !mudancas.data.length && (
        <Aviso tipo="sucesso" icone={<CheckCheck className="size-4 text-emdia" />}>Nenhuma mudança aguardando decisão para os seus ativos.</Aviso>
      )}
      <div className="space-y-4">{mudancas.data?.map((m) => <CartaoMudanca key={m.versao_id} m={m} />)}</div>

      <Secao titulo="Decisões registradas" className="mt-10"><Decisoes /></Secao>
      <Secao titulo="Histórico de Obrigação" className="mt-10">
        <HistoricoDeObrigacao />
      </Secao>
    </>
  );
}
