"use client";

import { BookCheck, ExternalLink, FileSearch, TriangleAlert } from "lucide-react";
import { Aviso, Carregando, Cartao, ErroCarga, Etiqueta, Expansivel, LinkBotao, Titulo, Vazio, cx } from "@/components/ui";
import { CLASSES, fonteLida, rotuloDaCobertura, tomDaCobertura } from "@/lib/cobertura";
import { type ItemCobertura, useCobertura } from "@/lib/consultas";
import { curto, plural } from "@/lib/formato";
import { TIPO_ATIVO } from "@/lib/status";
import { useEmpresa, useTorre } from "@/lib/torre";

type Norma = ItemCobertura["em_curadoria"][number];

function Bloco({ titulo, children, testid }: { titulo: string; children: React.ReactNode; testid?: string }) {
  return (
    <div data-testid={testid}>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-texto-3">{titulo}</p>
      {children}
    </div>
  );
}

function ListaDeNormas({ normas }: { normas: Norma[] }) {
  return (
    <ul className="divide-y divide-borda">
      {normas.map((n) => (
        <li key={n.chave} className="py-2.5 first:pt-0 last:pb-0" data-testid="norma-cobertura">
          <p className="flex flex-wrap items-center gap-x-2 text-sm font-semibold">
            {n.url ? (
              <a href={n.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-marca hover:underline">
                {n.titulo}<ExternalLink className="size-3.5" aria-hidden /><span className="sr-only">(texto oficial)</span>
              </a>
            ) : n.titulo}
          </p>
          {n.ementa && <p className="mt-0.5 text-[13px] text-texto-2">{curto(n.ementa, 260)}</p>}
          {n.deveres && <p className="mt-1 text-[13px]"><span className="font-semibold">O que cobra, pela IA:</span> {n.deveres}</p>}
          {n.cita_catalogo.length > 0 && (
            <p className="mt-1 flex gap-1.5 text-[13px] text-vence">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Altera ou regulamenta {n.cita_catalogo.join(", ")}: conferir se o texto consolidado do catálogo já tem.
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function Linha({ i, plataforma }: { i: ItemCobertura; plataforma: boolean }) {
  const tom = tomDaCobertura(i.estado, i.verificada);
  const c = CLASSES[tom];
  return (
    <Cartao className={cx("border-l-4 p-4 sm:p-5", c.esquerda)} data-testid={`cobertura-${i.jurisdicao}-${i.tipo_ativo}`} data-tom={tom}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">{TIPO_ATIVO[i.tipo_ativo] ?? i.tipo_ativo} · {i.jurisdicao_nome}</h2>
          <p className="mt-0.5 text-[13px] text-texto-2">Ativos: {i.ativos.join(", ")}</p>
        </div>
        <Etiqueta tom={c.etiqueta} className="max-w-full whitespace-normal text-left" title={i.estado}>
          <span className={cx("mr-1.5 inline-block size-1.5 shrink-0 rounded-full", c.ponto)} aria-hidden />
          <span data-testid="estado">{rotuloDaCobertura(i.estado_rotulo, i.verificada)}</span>
        </Etiqueta>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Bloco titulo="No catálogo" testid="catalogadas">
          {i.catalogadas.length ? (
            <ul className="flex flex-wrap gap-1.5">
              {i.catalogadas.map((n) => <li key={n}><Etiqueta tom="marca">{n}</Etiqueta></li>)}
            </ul>
          ) : <p className="text-sm text-texto-2">Nenhuma norma desta jurisdição no catálogo ainda.</p>}
        </Bloco>
        <Bloco titulo="Fontes lidas" testid="fontes">
          {i.fontes.length ? (
            <ul className="space-y-0.5 text-sm">
              {i.fontes.map((f) => <li key={f.fonte} title={f.cobre}>{fonteLida(f)}</li>)}
            </ul>
          ) : (
            <p className="text-sm text-texto-2">
              {i.estado === "sem_fonte" ? "Nenhuma fonte automática para esta jurisdição." : "A fonte desta jurisdição ainda não foi lida."}
            </p>
          )}
        </Bloco>
        <Bloco titulo="Lacunas conhecidas" testid="lacunas">
          {i.lacunas.length ? (
            <ul className="list-disc space-y-0.5 pl-4 text-sm">{i.lacunas.map((l) => <li key={l}>{l}</li>)}</ul>
          ) : <p className="text-sm text-texto-2">Nenhuma registrada.</p>}
        </Bloco>
      </div>

      {(i.triagem_pendente > 0 || i.em_curadoria.length > 0 || i.aprovadas.length > 0) && (
        <div className="mt-4 space-y-2">
          {i.triagem_pendente > 0 && (
            <p className="text-sm text-texto-2">{plural(i.triagem_pendente, "candidata esperando", "candidatas esperando")} a triagem da IA.</p>
          )}
          {i.em_curadoria.length > 0 && (
            <Expansivel resumo={
              <span className="flex flex-wrap items-center gap-2">
                <Etiqueta tom="atencao">esperando curadoria</Etiqueta>
                <span className="font-medium">{plural(i.em_curadoria.length, "norma já publicada que a IA achou relevante", "normas já publicadas que a IA achou relevantes")}, fora do catálogo</span>
              </span>
            }>
              <div data-testid="em-curadoria"><ListaDeNormas normas={i.em_curadoria} /></div>
              {plataforma && (
                <LinkBotao href={`/regulatorio/normas-candidatas/?jurisdicao=${i.jurisdicao}`} tamanho="p" className="mt-3" icone={<FileSearch className="size-3.5" />}>
                  Abrir na fila da curadoria
                </LinkBotao>
              )}
            </Expansivel>
          )}
          {i.aprovadas.length > 0 && (
            <Expansivel resumo={
              <span className="flex flex-wrap items-center gap-2">
                <Etiqueta tom="proposta">aprovada, falta extrair</Etiqueta>
                <span className="font-medium">{plural(i.aprovadas.length, "norma aprovada pela curadoria", "normas aprovadas pela curadoria")}: as obrigações ainda vão ser extraídas</span>
              </span>
            }>
              <div data-testid="aprovadas"><ListaDeNormas normas={i.aprovadas} /></div>
            </Expansivel>
          )}
        </div>
      )}
    </Cartao>
  );
}

export default function Cobertura() {
  const t = useTorre();
  const empresa = useEmpresa();
  const cobertura = useCobertura();
  return (
    <>
      <Titulo sobre="Regulatório" titulo="Cobertura normativa">
        Que normas valem para os ativos da {empresa.nome}, por jurisdição e tipo de ativo: o que já está no catálogo, até onde
        cada fonte oficial foi lida, o que a plataforma sabe que não cobre e as normas já publicadas que ainda esperam a curadoria
        RegulaIA. Jurisdição sem fonte automática aparece como cobertura não verificada, nunca como coberta.
      </Titulo>
      {cobertura.isLoading && <Carregando linhas={5} />}
      {cobertura.error && <ErroCarga erro={cobertura.error} onTentar={() => cobertura.refetch()} />}
      {cobertura.data && !cobertura.data.length && (
        <Vazio icone={<BookCheck className="size-4" />}>Nenhum ativo seu com norma pública para cobrir (licenças valem pelas condicionantes da própria empresa).</Vazio>
      )}
      {cobertura.data && cobertura.data.length > 0 && (
        <>
          <Aviso tipo="info" className="mb-4">
            Verde: as fontes automáticas foram lidas e nada relevante ficou fora do catálogo (as lacunas conhecidas seguem ao lado).
            Amarelo: há norma esperando triagem, curadoria ou extração. Cinza: cobertura não verificada.
          </Aviso>
          <div className="space-y-4" data-testid="cobertura">
            {cobertura.data.map((i) => <Linha key={`${i.jurisdicao}-${i.tipo_ativo}`} i={i} plataforma={t.plataforma} />)}
          </div>
        </>
      )}
    </>
  );
}
