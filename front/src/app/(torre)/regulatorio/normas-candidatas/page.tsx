"use client";

import { Bot, Check, ExternalLink, FileText, TriangleAlert, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { useAvisar } from "@/components/avisos";
import {
  AreaTexto, Aviso, Botao, Campo, CampoEntrada, CampoSelecao, Carregando, Cartao, ErroCarga, Etiqueta, Titulo, Vazio, mensagem,
} from "@/components/ui";
import { confianca } from "@/lib/cobertura";
import { type NormaCandidata, type StatusCandidata, useDecidirCandidata, useNormasCandidatas } from "@/lib/consultas";
import { dataBR, emBrasilia, numero, plural } from "@/lib/formato";
import { TIPO_ATIVO } from "@/lib/status";
import { useTorre } from "@/lib/torre";

// a curadoria trabalha nestas; "irrelevante" é o que a IA descartou e a curadoria pode reabrir
const FILTROS: StatusCandidata[] = ["relevante", "aprovada", "descartada", "irrelevante"];
const POR_PAGINA = 30;
const TOM_STATUS: Record<string, "atencao" | "proposta" | "neutro" | "ok" | "perigo"> = {
  relevante: "atencao", aprovada: "proposta", descartada: "perigo", irrelevante: "neutro", catalogada: "ok", nova: "neutro",
};

function CartaoNorma({ n, decide }: { n: NormaCandidata; decide: boolean }) {
  const avisar = useAvisar();
  const decidir = useDecidirCandidata({
    onSuccess: (r) => avisar(`${r.titulo}: ${r.status_rotulo}. Fica registrado quem decidiu.`),
    onError: (e) => avisar(`Decisão não aceita: ${mensagem(e)}`, "erro"),
  });
  const [nota, setNota] = useState("");
  const t = n.triagem;
  const pode = decide && n.status !== "catalogada" && n.status !== "nova";
  const enviar = (decisao: "aprovar" | "descartar") => decidir.mutate({ chave: n.chave, decisao, nota });

  return (
    <Cartao className="p-4 sm:p-5" data-testid="norma-candidata">
      <div className="flex flex-wrap items-center gap-1.5">
        <Etiqueta tom={TOM_STATUS[n.status] ?? "neutro"}>{n.status_rotulo}</Etiqueta>
        <Etiqueta>{n.jurisdicao_nome}</Etiqueta>
        <Etiqueta>{n.fonte_nome}</Etiqueta>
        {n.temas.map((x) => <Etiqueta key={x} tom="marca">{TIPO_ATIVO[x] ?? x}</Etiqueta>)}
      </div>
      <h2 className="mt-2 text-base font-semibold">{n.titulo}</h2>
      <p className="mt-0.5 flex flex-wrap items-center gap-x-3 text-[13px] text-texto-2">
        <span>{n.data ? `de ${dataBR(n.data)}` : `de ${n.ano}`}{n.situacao ? ` · ${n.situacao.toLowerCase()} pela fonte` : ""}</span>
        {n.url && (
          <a href={n.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-marca hover:underline">
            <FileText className="size-3.5" aria-hidden />Texto oficial<ExternalLink className="size-3" aria-hidden />
          </a>
        )}
      </p>
      {n.ementa && <p className="mt-3 text-sm">{n.ementa}</p>}

      {n.cita_catalogo.length > 0 && (
        <Aviso tipo="atencao" className="mt-3" icone={<TriangleAlert className="size-4 text-vence" />}>
          Altera ou regulamenta {n.cita_catalogo.join(", ")}: conferir se o texto consolidado do catálogo já tem antes de extrair.
        </Aviso>
      )}

      {t ? (
        <div className="mt-3 space-y-1.5 rounded-md bg-fundo-2 px-4 py-3 text-[13px]" data-testid="triagem">
          <p className="flex items-center gap-1.5 font-semibold">
            <Bot className="size-4 text-marca" aria-hidden />
            A IA {t.relevante ? "achou relevante" : "achou irrelevante"}
            {t.tipos_ativo.length > 0 && ` para ${t.tipos_ativo.map((x) => (TIPO_ATIVO[x] ?? x).toLowerCase()).join(" e ")}`}
          </p>
          {t.deveres && <p><span className="font-semibold">Deveres:</span> {t.deveres}</p>}
          {t.motivo && <p><span className="font-semibold">Motivo:</span> {t.motivo}</p>}
          <p className="text-texto-2">
            Confiança {confianca(t.confianca)} · modelo {t.modelo} ·{" "}
            <span data-testid="leu-texto">{t.leu_texto ? "leu o texto oficial" : "decidiu só pela ementa"}</span>
            {t.custo_usd > 0 ? ` · US$ ${numero(t.custo_usd, 4)}` : ""}
          </p>
        </div>
      ) : <p className="mt-3 text-[13px] text-texto-2">Ainda não passou pela triagem da IA.</p>}

      {n.decidida_por && (
        <p className="mt-3 text-[13px] text-texto-2">
          {n.status === "aprovada" ? "Aprovada" : n.status === "descartada" ? "Descartada" : "Decidida"} por {n.decidida_por} em {emBrasilia(n.decidida_em)}
          {n.nota ? `: “${n.nota}”` : ""}
        </p>
      )}

      {pode && (
        <div className="mt-4 space-y-2">
          <Campo rotulo="Nota da curadoria" htmlFor={`nota-${n.chave}`} dica="Fica na decisão e na auditoria, com o seu e-mail.">
            <AreaTexto id={`nota-${n.chave}`} rows={2} value={nota} onChange={(e) => setNota(e.target.value)} maxLength={2000}
              placeholder={n.status === "irrelevante" ? "Por que reabrir o que a IA descartou?" : "Ex.: extrair o art. 7º"} />
          </Campo>
          <div className="flex flex-wrap gap-2">
            {n.status !== "aprovada" && (
              <Botao variante="primario" icone={<Check className="size-4" />} disabled={decidir.isPending}
                carregando={decidir.isPending && decidir.variables?.decisao === "aprovar"} onClick={() => enviar("aprovar")}>
                Aprovar
              </Botao>
            )}
            {n.status !== "descartada" && (
              <Botao variante="perigo" icone={<X className="size-4" />} disabled={decidir.isPending}
                carregando={decidir.isPending && decidir.variables?.decisao === "descartar"} onClick={() => enviar("descartar")}>
                Descartar
              </Botao>
            )}
          </div>
        </div>
      )}
    </Cartao>
  );
}

function Fila() {
  const t = useTorre();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const status = (FILTROS as string[]).includes(params.get("status") ?? "") ? (params.get("status") as StatusCandidata) : "relevante";
  const jurisdicao = (params.get("jurisdicao") ?? "").toUpperCase();
  const fila = useNormasCandidatas(status, jurisdicao);
  const [busca, setBusca] = useState("");
  const [mostrar, setMostrar] = useState(POR_PAGINA);

  const mudar = (novo: { status?: string; jurisdicao?: string }) => {
    const q = new URLSearchParams({ status, jurisdicao, ...novo });
    for (const [k, v] of [...q.entries()]) if (!v || (k === "status" && v === "relevante")) q.delete(k);
    const s = q.toString();
    router.replace(`${caminho}${s ? `?${s}` : ""}`, { scroll: false });
    setMostrar(POR_PAGINA);
  };

  const termo = busca.trim().toLowerCase();
  const normas = useMemo(() => (fila.data?.normas ?? []).filter((n) =>
    !termo || `${n.titulo} ${n.chave} ${n.ementa} ${n.triagem?.deveres ?? ""}`.toLowerCase().includes(termo)), [fila.data, termo]);

  if (!t.plataforma) return <Aviso tipo="info">A fila de normas candidatas é trabalho da curadoria da Mitra.</Aviso>;
  const contagem = fila.data?.contagem ?? {};
  const rotulos = fila.data?.status_rotulos ?? {};
  const decide = fila.data?.decide ?? false;

  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <CampoSelecao rotulo="Jurisdição" value={jurisdicao} onChange={(e) => mudar({ jurisdicao: e.target.value })}>
          <option value="">Todas</option>
          {(fila.data?.jurisdicoes ?? []).map((j) => <option key={j.sigla} value={j.sigla}>{j.nome}</option>)}
        </CampoSelecao>
        <CampoSelecao rotulo="Status" value={status} onChange={(e) => mudar({ status: e.target.value })}>
          {FILTROS.map((s) => (
            <option key={s} value={s}>{rotulos[s] ?? s}{contagem[s] !== undefined ? ` (${numero(contagem[s]!)})` : ""}</option>
          ))}
        </CampoSelecao>
        <CampoEntrada rotulo="Buscar na fila" type="search" placeholder="número, título, ementa…" value={busca}
          onChange={(e) => { setBusca(e.target.value); setMostrar(POR_PAGINA); }} />
      </div>
      {fila.isLoading && <Carregando linhas={4} />}
      {fila.error && <ErroCarga erro={fila.error} onTentar={() => fila.refetch()} />}
      {fila.data && (
        <>
          <p className="mb-3 text-[13px] text-texto-2" data-testid="total-fila">
            {plural(normas.length, "norma", "normas")}
            {status === "relevante" ? ", as de menor confiança da IA primeiro (as que mais precisam de olho)" : ""}.
          </p>
          {!normas.length ? <Vazio>Nada nesta fila com estes filtros.</Vazio> : (
            <div className="space-y-4">
              {normas.slice(0, mostrar).map((n) => <CartaoNorma key={n.chave} n={n} decide={decide} />)}
            </div>
          )}
          {normas.length > mostrar && (
            <Botao className="mt-4" onClick={() => setMostrar((m) => m + POR_PAGINA)}>
              Mostrar mais {Math.min(POR_PAGINA, normas.length - mostrar)} de {numero(normas.length - mostrar)}
            </Botao>
          )}
        </>
      )}
    </>
  );
}

export default function NormasCandidatas() {
  return (
    <>
      <Titulo sobre="Curadoria Mitra" titulo="Normas candidatas">
        Leis, decretos e resoluções já publicados que a busca nas fontes oficiais achou para os ativos da carteira e a IA triou pela
        ementa (ou pelo texto, nos descartes duvidosos). Aprovada vai para a extração das obrigações; descartada sai da fila. Vale
        para todas as clientes, e cada decisão fica na auditoria com o seu e-mail.
      </Titulo>
      <Suspense fallback={<Carregando linhas={6} />}>
        <Fila />
      </Suspense>
    </>
  );
}
