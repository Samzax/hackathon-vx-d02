"use client";

import { CalendarPlus, CheckCheck, FileDown, FileText, FileUp, Mail } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { type AlvoEntrega, DialogoEntrega } from "@/components/entrega";
import { Dialogo } from "@/components/dialogo";
import { LeitorDeDocumento } from "@/components/leitor";
import { Markdown } from "@/components/markdown";
import {
  Aviso, Botao, Carregando, Cartao, ErroCarga, Etiqueta, Expansivel, LinkBotao, Numero, Titulo, cx, mensagem,
} from "@/components/ui";
import { useAvisar } from "@/components/avisos";
import { useQuery } from "@tanstack/react-query";
import { baixar, texto } from "@/lib/api";
import { type Linha, useMudancas, usePainel } from "@/lib/consultas";
import { curto, dataBR, maiuscula, nomeDeArquivo } from "@/lib/formato";
import { ATRASADA, DADO_FALTANDO, PRINCIPAIS, ROTULO, VENCE_LOGO, cor } from "@/lib/status";
import { useEmpresa, useTorre } from "@/lib/torre";
import { LinkOficial } from "@/components/link-oficial";

const ULTIMA_EXECUCAO = "ultima_execucao";
const MAX_ITENS = 6;
const GRUPOS = [
  { status: ATRASADA, titulo: "Obrigações atrasadas" },
  { status: DADO_FALTANDO, titulo: "Obrigações com dados faltantes" },
  { status: VENCE_LOGO, titulo: "Obrigações vencendo em breve" },
];

function faltaCadastro(l: Linha): boolean {
  return l.status === DADO_FALTANDO && !(l.dados_faltando.length === 1 && l.dados_faltando[0] === ULTIMA_EXECUCAO);
}

function oQueFalta(l: Linha): string {
  if (faltaCadastro(l)) return `falta no cadastro: ${l.dados_faltando_rotulos.join("; ")}`;
  if (l.status === DADO_FALTANDO) return "falta a data da última execução";
  const partes = [l.pendente, l.status === VENCE_LOGO && l.vence ? `vence ${dataBR(l.vence)}` : ""].filter(Boolean);
  return partes.join(" · ") || "—";
}

/** Sem `onEntregar` (a plataforma só lê), o item não oferece registrar nem completar o cadastro. */
function Item({ l, onEntregar }: { l: Linha; onEntregar?: (l: Linha) => void }) {
  const ficha = `/ativos/?id=${l.ativo_id}`;
  const motivo = maiuscula(oQueFalta(l));
  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:gap-4" data-testid="item-caixa">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-start gap-2 text-sm">
          {onEntregar ? (
            <button type="button" onClick={() => onEntregar(l)} className="min-w-0 text-left font-semibold hover:text-marca hover:underline focus-visible:rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marca">
              {l.titulo}
            </button>
          ) : <strong>{l.titulo}</strong>}
          <Etiqueta tom="neutro" className="shrink-0">{l.ativo}</Etiqueta>
        </p>
        <p className={cx("mt-1 text-xs font-semibold", cor(l.status).texto)}>{motivo}</p>
        <p className="mt-1 text-xs text-texto-2">
          {l.responsavel ?? "Sem responsável"} · <LinkOficial href={l.norma_link}>{l.dispositivo}</LinkOficial>
        </p>
      </div>
      <div className="flex shrink-0 gap-1.5">
        <LinkBotao href={ficha} tamanho="p" variante="fantasma">Ver ativo</LinkBotao>
      </div>
    </li>
  );
}

function Boletim() {
  const t = useTorre();
  const empresa = useEmpresa();
  const avisar = useAvisar();
  const para = t.veTudo ? null : t.eu.area ?? t.eu.visao;
  const quem = para ?? "Diretoria";
  const [aberto, setAberto] = useState(false);
  const consulta = { hoje: t.hoje };
  const md = useQuery({
    queryKey: [...t.chave, "boletim"],
    queryFn: () => texto(`/api/v1/empresas/${empresa.id}/boletim`, consulta),
    enabled: aberto,
  });
  const sufixo = `${t.hoje}_${nomeDeArquivo(quem.toLowerCase() === "diretoria" ? "diretoria" : quem)}`;
  const baixe = (caminho: string, nome: string, extra: Record<string, string> = {}) =>
    baixar(caminho, { ...consulta, ...extra }, nome).catch((e) => avisar(mensagem(e), "erro"));

  return (
    <Expansivel
      aberto={aberto}
      onToggle={setAberto}
      resumo={<span className="flex items-center gap-2 font-medium"><Mail className="size-4 text-marca" aria-hidden />Boletim da semana — {quem}</span>}
    >
      <div className="mt-3 flex flex-wrap gap-2">
        <Botao variante="primario" tamanho="p" icone={<FileDown className="size-3.5" />}
          onClick={() => baixe(`/api/v1/empresas/${empresa.id}/boletim`, `boletim_${sufixo}.pdf`, { formato: "pdf" })}>
          Baixar boletim (PDF)
        </Botao>
        <Botao tamanho="p" icone={<FileText className="size-3.5" />}
          onClick={() => baixe(`/api/v1/empresas/${empresa.id}/boletim`, `boletim_${sufixo}.md`)}>
          Boletim em texto (.md)
        </Botao>
        <Botao tamanho="p" icone={<CalendarPlus className="size-3.5" />} title="Importa no Outlook ou Google Agenda: um evento por vencimento"
          onClick={() => baixe(`/api/v1/empresas/${empresa.id}/calendario.ics`, `vencimentos_${sufixo}.ics`)}>
          Vencimentos no calendário (.ics)
        </Botao>
      </div>
      <div className="mt-4 rounded-md bg-fundo-2 px-4 py-3">
        {md.isLoading && <Carregando linhas={4} />}
        {md.error && <ErroCarga erro={md.error} onTentar={() => md.refetch()} />}
        {md.data && <Markdown texto={md.data} semTitulo />}
      </div>
    </Expansivel>
  );
}

export default function Caixa() {
  const t = useTorre();
  const painel = usePainel();
  const mudancas = useMudancas();
  const [alvo, setAlvo] = useState<AlvoEntrega | null>(null);
  const [documentoAberto, setDocumentoAberto] = useState(false);

  const grupos = useMemo(() => {
    const linhas = painel.data?.linhas ?? [];
    return GRUPOS.map((g) => ({
      ...g,
      linhas: linhas.filter((l) => l.status === g.status)
        .sort((a, b) => (a.vence ?? "9999").localeCompare(b.vence ?? "9999") || a.ativo.localeCompare(b.ativo)),
    })).filter((g) => g.linhas.length);
  }, [painel.data]);

  const pendentes = mudancas.data ?? [];
  const meus = new Set((painel.data?.linhas ?? []).map((l) => l.ativo));

  return (
    <>
      <Titulo titulo="Caixa de entrada" acoes={
        <Botao variante="primario" icone={<FileUp className="size-4" />} onClick={() => setDocumentoAberto(true)}>
          Adicionar documento
        </Botao>
      } />

      {painel.error ? <ErroCarga erro={painel.error} onTentar={() => painel.refetch()} /> : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5" data-testid="numeros" aria-label="Filtrar obrigações por status">
          {PRINCIPAIS.map((s) => (
            <Numero
              key={s}
              status={s}
              rotulo={maiuscula(ROTULO[s] ?? s)}
              valor={painel.data ? (painel.data.contagem[s] ?? 0) : "…"}
              href={`/entregas/?status=${s}`}
            />
          ))}
        </div>
      )}

      <h2 className="mb-3 mt-8 text-base font-semibold">Revisões pendentes</h2>
      {painel.isLoading && <Carregando linhas={5} />}
      <div className="space-y-4">
        {pendentes.length > 0 && (
          <Cartao className="px-4 py-3" data-testid="grupo-mudancas">
            <div className="flex flex-wrap items-center gap-2">
              <Etiqueta tom="marca">
                Mudanças normativas aguardando decisão
              </Etiqueta>
            </div>
            <ul className="divide-y divide-borda">
              {pendentes.map((m) => (
                <li key={m.versao_id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm">
                      <strong>{m.codigo}</strong> · {curto(m.titulo, 70)}{" "}
                      <span className="text-texto-2">({m.ativos.filter((a) => meus.has(a)).join(", ") || m.ativos.join(", ")})</span>
                    </p>
                    <div className="mt-1 space-y-0.5 text-xs text-texto-2">
                      <p>{m.ato ?? m.fonte}</p>
                      {[
                        { campo: "prazo", rotulo: "Prazo de cumprimento" },
                        { campo: "vigencia_desde", rotulo: "Início da vigência" },
                      ].map(({ campo, rotulo }) => {
                        const alteracao = m.campos.find((c) => c.campo === campo);
                        return alteracao && <p key={campo}>{rotulo}: <strong className="text-texto">{alteracao.proposto_texto}</strong></p>;
                      })}
                    </div>
                  </div>
                  <LinkBotao href={`/regulatorio/mudancas/#m${m.versao_id}`} tamanho="p" variante="primario">Revisar alteração</LinkBotao>
                </li>
              ))}
            </ul>
          </Cartao>
        )}

        {grupos.map((g) => (
          <Cartao key={g.status} className="px-4 py-3" data-testid={`grupo-${g.status}`}>
            <h3 className="flex items-center gap-2 text-sm font-semibold"><span className={cx("size-2 rounded-full", cor(g.status).ponto)} aria-hidden />{g.titulo}</h3>
            <ul className="divide-y divide-borda">
              {g.linhas.slice(0, MAX_ITENS).map((l) => (
                <Item key={`${l.ativo_id}-${l.codigo}`} l={l} onEntregar={t.soLeitura ? undefined : setAlvo} />
              ))}
            </ul>
            {g.linhas.length > MAX_ITENS && (
              <Link href={`/entregas/?status=${g.status}`} className="mt-1 inline-block text-[13px] font-medium text-marca hover:underline">
                Ver as outras {g.linhas.length - MAX_ITENS} na lista →
              </Link>
            )}
          </Cartao>
        ))}

        {painel.data && !grupos.length && !pendentes.length && (
          <Aviso tipo="sucesso" icone={<CheckCheck className="size-4 text-emdia" />}>
            Nada atrasado, nada faltando e nada vencendo nos próximos dias.
          </Aviso>
        )}

        <Boletim />
      </div>

      <DialogoEntrega alvo={alvo} onFechar={() => setAlvo(null)} />
      <Dialogo aberto={documentoAberto} onFechar={() => setDocumentoAberto(false)} titulo="Adicionar documento" largura="lg">
        <LeitorDeDocumento />
      </Dialogo>
    </>
  );
}
