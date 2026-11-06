"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, History, List } from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { useAvisar } from "@/components/avisos";
import { EditorCadastro } from "@/components/cadastro";
import { Dialogo } from "@/components/dialogo";
import { type AlvoEntrega, DialogoEntrega } from "@/components/entrega";
import { Eventos, Evidencias, HistoricoDaObrigacao } from "@/components/historico";
import type { Ponto } from "@/components/mapa";
import {
  Abas, Aviso, Botao, Carregando, Cartao, CampoSelecao, Entrada, ErroCarga, Expansivel, LinkBotao, Selo, Titulo, Vazio, cx, mensagem,
} from "@/components/ui";
import { api, dados } from "@/lib/api";
import { type Ativo, type Linha, useAreas, useAtivos, useFicha, useInvalidarTorre, usePainel } from "@/lib/consultas";
import { dataBR, maiuscula, plural } from "@/lib/formato";
import { ATRASADA, COLUNA, DADO_FALTANDO, GATILHO, ORDEM, ROTULO, TIPO_ATIVO, VENCE_LOGO, cor, ordenar, orgao, pior } from "@/lib/status";
import { RES_220, useTorre } from "@/lib/torre";

const Mapa = dynamic(() => import("@/components/mapa"), { ssr: false, loading: () => <div className="h-[320px] animate-pulse rounded-lg bg-fundo-2" /> });

const ULTIMA_EXECUCAO = "ultima_execucao";
const COLUNAS = Object.keys(COLUNA);

function Contagem({ n, status }: { n: number; status: string }) {
  return <td className={cx("num px-3 py-2 text-right", n ? cn(status) : "text-texto-3")}>{n}</td>;
}

function cn(status: string) {
  return cx("font-semibold", cor(status).texto);
}

// ------------------------------------------------------------------ ficha

function Pendencia({ l, onEntregar }: { l: Linha; onEntregar: (l: Linha) => void }) {
  const soData = l.dados_faltando.length === 1 && l.dados_faltando[0] === ULTIMA_EXECUCAO;
  const herdada = !!(l.nota && l.ultima_rotulo && l.nota.includes(dataBR(l.ultima)));
  return (
    <li className={cx("flex flex-col gap-3 border-l-[3px] py-3 pl-3 sm:flex-row", cor(l.status).esquerda)} data-testid="pendencia">
      <div className="min-w-0 flex-1 space-y-1 text-sm">
        <p className="flex flex-wrap items-center gap-2">
          <Selo status={l.status} />
          <strong>{l.titulo}</strong>
        </p>
        <p className="text-xs font-medium text-texto-2">{l.dispositivo}</p>
        {l.faltando_rotulos.length > 1 && <p>Períodos sem evidência: {l.faltando_rotulos.join(", ")}.</p>}
        {l.faltando_rotulos.length === 1 && !herdada && l.pendente && <p>{maiuscula(l.pendente)}.</p>}
        {l.status === VENCE_LOGO && l.vence && <p>Vence em {dataBR(l.vence)}.</p>}
        {l.nota && !l.dados_faltando.length && <p>{maiuscula(l.nota)}.</p>}
        {soData && (
          <p>Falta a <strong>data da última execução</strong>: sem ela não dá para calcular o próximo vencimento. Registre a última entrega ao lado.</p>
        )}
        {!soData && l.dados_faltando.length > 0 && (
          <p>
            Falta no cadastro do ativo: <strong>{l.dados_faltando_rotulos.join("; ")}</strong>. Sem esse dado não dá para dizer se a
            obrigação vale: preencha na aba Cadastro.
          </p>
        )}
        {l.trecho && (
          <blockquote className="mt-1 border-l-2 border-borda-forte pl-3 text-[13px] italic text-texto-2">“{l.trecho}”</blockquote>
        )}
      </div>
      {(!l.dados_faltando.length || soData) && (
        <div className="shrink-0">
          <Botao tamanho="p" icone={<Check className="size-3.5" />} onClick={() => onEntregar(l)}>Registrar entrega</Botao>
        </div>
      )}
    </li>
  );
}

function TabelaObrigacoes({ linhas, onHistorico, gatilho }: { linhas: Linha[]; onHistorico: (l: Linha) => void; gatilho?: boolean }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-borda">
      <table className="w-full min-w-[720px] text-sm">
        <thead className="bg-fundo-2 text-left text-xs text-texto-2">
          <tr>
            {!gatilho && <th className="px-3 py-2 font-medium">Status</th>}
            <th className="px-3 py-2 font-medium">Obrigação</th>
            <th className="px-3 py-2 font-medium">Dispositivo</th>
            {!gatilho && <th className="px-3 py-2 font-medium">Vence</th>}
            <th className="px-3 py-2 font-medium">{gatilho ? "Evidência" : "Pendente"}</th>
            <th className="px-3 py-2"><span className="sr-only">Histórico</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-borda">
          {linhas.map((l) => (
            <tr key={l.codigo}>
              {!gatilho && <td className="px-3 py-2"><Selo status={l.status} /></td>}
              <td className="px-3 py-2">
                <span className="text-xs text-texto-3">{l.codigo}</span> {l.titulo}
                {l.mudanca_pendente && <span className="ml-1 text-xs font-semibold text-proposta">· mudança aguardando</span>}
              </td>
              <td className="px-3 py-2 text-texto-2">{l.dispositivo}</td>
              {!gatilho && <td className="num px-3 py-2 whitespace-nowrap">{dataBR(l.vence)}</td>}
              <td className="px-3 py-2 text-texto-2">{gatilho ? l.evidencia : l.pendente || "—"}</td>
              <td className="px-3 py-2 text-right">
                <Botao tamanho="p" variante="fantasma" icone={<History className="size-3.5" />} onClick={() => onHistorico(l)} aria-label={`Histórico de ${l.codigo}`}>
                  Histórico
                </Botao>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AreaResponsavel({ ativo }: { ativo: Ativo }) {
  const areas = useAreas();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const [area, setArea] = useState(ativo.responsavel ?? "");
  const [nova, setNova] = useState("");
  const salvar = useMutation({
    mutationFn: (a: string) => dados(api.PUT("/api/v1/ativos/{ativo_id}/responsavel", { params: { path: { ativo_id: ativo.id } }, body: { area: a || null } })),
    onSuccess: (_, a) => { avisar(`${ativo.codigo} agora com ${a || "ninguém"}`); setNova(""); invalidar(); },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  const escolhida = area === "__nova__" ? nova.trim() : area;
  const lista = areas.data?.areas ?? [];
  const semConta = escolhida && areas.data && !areas.data.com_conta.includes(escolhida);
  return (
    <Cartao className="p-4">
      <p className="text-sm font-semibold">Área responsável pelo ativo</p>
      <p className="mt-0.5 text-xs text-texto-2">
        O gestor dessa área passa a ver o ativo inteiro. Obrigação com responsável próprio continua com ele. Só a Diretoria decide.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <CampoSelecao rotulo="Área" value={area} onChange={(e) => setArea(e.target.value)} className="min-w-64 flex-1">
          <option value="">ninguém</option>
          {lista.map((a) => <option key={a} value={a}>{a}</option>)}
          <option value="__nova__">outra área…</option>
        </CampoSelecao>
        {area === "__nova__" && (
          <Entrada aria-label="Nome da área nova" placeholder="ex.: Gerência de Barragens" value={nova} onChange={(e) => setNova(e.target.value)} className="min-w-56 flex-1" />
        )}
        <Botao onClick={() => salvar.mutate(escolhida)} disabled={escolhida === (ativo.responsavel ?? "") || (area === "__nova__" && !nova.trim())}
          carregando={salvar.isPending}>
          Salvar área
        </Botao>
      </div>
      {semConta && (
        <p className="mt-2 text-xs text-texto-2">Ninguém entra na torre como {escolhida} ainda: peça à TI uma conta de gestor com essa área.</p>
      )}
    </Cartao>
  );
}

type Aba = "pendencias" | "obrigacoes" | "evidencias" | "historico" | "cadastro";

const ABAS: Aba[] = ["pendencias", "obrigacoes", "evidencias", "historico", "cadastro"];

function Ficha({ ativoId, abaInicial }: { ativoId: number; abaInicial: Aba }) {
  const t = useTorre();
  const ficha = useFicha(ativoId);
  const [aba, setAba] = useState<Aba>(abaInicial);
  const [alvo, setAlvo] = useState<AlvoEntrega | null>(null);
  const [historico, setHistorico] = useState<Linha | null>(null);

  if (ficha.isLoading) return <Carregando linhas={4} />;
  if (ficha.error) return <ErroCarga erro={ficha.error} onTentar={() => ficha.refetch()} />;
  const { ativo: a, linhas, evidencias, eventos } = ficha.data!;
  const ruins = linhas.filter((l) => [ATRASADA, DADO_FALTANDO, VENCE_LOGO].includes(l.status))
    .sort((x, y) => (ORDEM[x.status] ?? 9) - (ORDEM[y.status] ?? 9));
  const comData = ordenar(linhas.filter((l) => l.status !== GATILHO));
  const gatilho = linhas.filter((l) => l.status === GATILHO);
  const faltaCad = [...new Set(linhas.flatMap((l) => l.dados_faltando).filter((c) => c !== ULTIMA_EXECUCAO))].sort();
  const titulos = Object.fromEntries(linhas.map((l) => [l.codigo, l.titulo]));

  return (
    <Cartao className="p-4 sm:p-5" data-testid="ficha">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{a.codigo} · {a.nome}</h2>
          <p className="mt-0.5 text-[13px] text-texto-2">
            {TIPO_ATIVO[a.tipo] ?? a.tipo} · responsável: {a.responsavel ?? "ninguém"} · {plural(linhas.length, "obrigação", "obrigações")}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {COLUNAS.map((s) => (a.contagem[s] ?? 0) > 0 && <Selo key={s} status={s} texto={`${a.contagem[s]} ${ROTULO[s]!.toLowerCase()}`} />)}
          </div>
        </div>
        <LinkBotao href={`/entregas/?ativo=${encodeURIComponent(a.codigo)}`} tamanho="p" icone={<List className="size-3.5" />}>
          Ver este ativo em Entregas
        </LinkBotao>
      </div>

      <div className="mt-4">
        <Abas<Aba> rotulo="Ficha do ativo" ativa={aba} onTrocar={setAba} abas={[
          { id: "pendencias", rotulo: `Pendências (${ruins.length})` },
          { id: "obrigacoes", rotulo: `Obrigações (${linhas.length})` },
          { id: "evidencias", rotulo: "O que comprova" },
          { id: "historico", rotulo: "Histórico" },
          { id: "cadastro", rotulo: faltaCad.length ? `Cadastro (${faltaCad.length} faltando)` : "Cadastro" },
        ]} />
      </div>
      <div className="pt-4">
        {aba === "pendencias" && (ruins.length ? (
          <ul className="space-y-1">{ruins.map((l) => <Pendencia key={l.codigo} l={l} onEntregar={setAlvo} />)}</ul>
        ) : <Aviso tipo="sucesso">Nada atrasado, faltando ou vencendo neste ativo.</Aviso>)}

        {aba === "obrigacoes" && (
          <div className="space-y-5">
            {comData.length > 0 && <TabelaObrigacoes linhas={comData} onHistorico={setHistorico} />}
            {gatilho.length > 0 && (
              <div>
                <p className="mb-2 text-sm font-semibold">{gatilho.length} obrigações por gatilho <span className="font-normal text-texto-2">(incidente, emergência, modificação…)</span></p>
                <TabelaObrigacoes linhas={gatilho} onHistorico={setHistorico} gatilho />
              </div>
            )}
          </div>
        )}

        {aba === "evidencias" && <Evidencias evidencias={evidencias} titulos={titulos} />}
        {aba === "historico" && <Eventos eventos={eventos} vazio="Nenhuma entrega, comentário ou mudança de cadastro registrada neste ativo." />}
        {aba === "cadastro" && (
          <div className="space-y-4">
            {t.diretoria && <AreaResponsavel key={`${a.id}-${a.responsavel}`} ativo={a} />}
            <EditorCadastro key={a.id} ativo={a} faltando={faltaCad} />
          </div>
        )}
      </div>

      <DialogoEntrega alvo={alvo} onFechar={() => setAlvo(null)} />
      <Dialogo aberto={!!historico} onFechar={() => setHistorico(null)} largura="lg"
        titulo={historico ? `${a.codigo} · ${historico.codigo} · ${historico.titulo}` : ""}>
        {historico && (
          <>
            <p className="mb-3 text-[13px] text-texto-2">{historico.dispositivo} · {historico.agenda_descricao}</p>
            {historico.trecho && <blockquote className="mb-4 border-l-2 border-borda-forte pl-3 text-[13px] italic text-texto-2">“{historico.trecho}”</blockquote>}
            <HistoricoDaObrigacao ativoId={a.id} codigo={historico.codigo} />
          </>
        )}
      </Dialogo>
    </Cartao>
  );
}

// ------------------------------------------------------------------ tela

function PorNorma({ linhas }: { linhas: Linha[] }) {
  const t = useTorre();
  const normas = [...new Set(linhas.map((l) => l.norma).filter((n): n is string => !!n))].sort();
  return (
    <Expansivel resumo={<span className="font-medium">Por norma: quem cobra o quê</span>}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-xs text-texto-2">
            <tr>
              <th className="px-3 py-2 font-medium">Órgão</th><th className="px-3 py-2 font-medium">Norma</th>
              <th className="px-3 py-2 text-right font-medium">Obrigações</th><th className="px-3 py-2 font-medium">Ativos</th>
              {COLUNAS.map((s) => <th key={s} className="px-3 py-2 text-right font-medium">{COLUNA[s]}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-borda">
            {normas.map((n) => {
              const daNorma = linhas.filter((l) => l.norma === n);
              return (
                <tr key={n}>
                  <td className="px-3 py-2 text-texto-2">{orgao(n)}</td>
                  <td className="px-3 py-2">{n}</td>
                  <td className="num px-3 py-2 text-right">{new Set(daNorma.map((l) => l.codigo)).size}</td>
                  <td className="px-3 py-2 text-texto-2">{[...new Set(daNorma.map((l) => l.ativo))].sort().join(", ")}</td>
                  {COLUNAS.map((s) => <Contagem key={s} status={s} n={daNorma.filter((l) => l.status === s).length} />)}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {t.hoje < RES_220 && (
        <p className="mt-2 text-xs text-texto-2">
          A Res. ANM 220/2025 ainda não aparece: entra em {dataBR(RES_220)} no lugar da Res. 95/2022. O que muda está em
          Regulatório → Transição e linha do tempo.
        </p>
      )}
    </Expansivel>
  );
}

function Ativos() {
  const router = useRouter();
  const busca = useSearchParams();
  const ativos = useAtivos();
  const painel = usePainel();
  const lista = useMemo(() => ativos.data ?? [], [ativos.data]);

  const padrao = useMemo(() => {
    // abre no ativo com mais problema
    const nota = (a: Ativo) => [-(a.contagem.atrasada ?? 0), -((a.contagem.dado_faltando ?? 0) + (a.contagem.vence_logo ?? 0))];
    return [...lista].sort((x, y) => {
      const [a1, a2] = nota(x);
      const [b1, b2] = nota(y);
      return a1! - b1! || a2! - b2!;
    })[0]?.id ?? null;
  }, [lista]);
  const pedido = Number(busca.get("id")) || null;
  const escolhido = lista.some((a) => a.id === pedido) ? pedido : padrao;
  const escolher = (id: number) => router.replace(`/ativos/?id=${id}`, { scroll: false });
  const aba = busca.get("aba") as Aba | null;
  const abaInicial: Aba = aba && ABAS.includes(aba) ? aba : "pendencias";

  const pontos: Ponto[] = lista.filter((a) => a.posicao?.length === 2).map((a) => ({
    id: a.id, codigo: a.codigo, nome: a.nome, tipo: a.tipo, status: pior(a.contagem), posicao: [a.posicao![0]!, a.posicao![1]!],
  }));

  if (ativos.error) return <ErroCarga erro={ativos.error} onTentar={() => ativos.refetch()} />;

  return (
    <>
      <Titulo sobre="Operação" titulo="Ativos">
        Clique num ativo para abrir a ficha. Vencendo = vence em até 30 dias (5 para quinzenal e mensal).
      </Titulo>
      {ativos.isLoading && <Carregando linhas={6} />}

      {pontos.length > 0 && (
        <div className="mb-5">
          <Mapa pontos={pontos} escolhido={escolhido} onEscolher={escolher} />
          <p className="mt-1.5 text-xs text-texto-3">Posições fictícias, na região do Quadrilátero Ferrífero (MG). Clique num ponto para abrir a ficha.</p>
        </div>
      )}

      {lista.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-borda">
          <table className="w-full min-w-[680px] text-sm" data-testid="tabela-ativos">
            <thead className="bg-fundo-2 text-left text-xs text-texto-2">
              <tr>
                <th className="px-3 py-2 font-medium">Ativo</th>
                <th className="px-3 py-2 font-medium">Responsável</th>
                {COLUNAS.map((s) => <th key={s} className="px-3 py-2 text-right font-medium">{COLUNA[s]}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-borda">
              {lista.map((a) => (
                <tr key={a.id} onClick={() => escolher(a.id)} aria-selected={a.id === escolhido}
                  className={cx("cursor-pointer hover:bg-fundo-2", a.id === escolhido && "bg-marca-suave hover:bg-marca-suave")}>
                  <td className="px-3 py-2">
                    <button type="button" className="text-left font-medium hover:underline" onClick={(e) => { e.stopPropagation(); escolher(a.id); }}>
                      {a.codigo} · {a.nome}
                    </button>
                    <span className="block text-xs text-texto-3">{TIPO_ATIVO[a.tipo] ?? a.tipo}</span>
                  </td>
                  <td className="px-3 py-2 text-texto-2">{a.responsavel ?? "—"}</td>
                  {COLUNAS.map((s) => <Contagem key={s} status={s} n={a.contagem[s] ?? 0} />)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {ativos.data && !lista.length && <Vazio>Nenhum ativo para esta visão.</Vazio>}

      {painel.data && lista.length > 0 && <div className="mt-4"><PorNorma linhas={painel.data.linhas} /></div>}

      {escolhido !== null && <div className="mt-6"><Ficha key={`${escolhido}-${abaInicial}`} ativoId={escolhido} abaInicial={abaInicial} /></div>}
    </>
  );
}

export default function PaginaAtivos() {
  return (
    <Suspense fallback={<Carregando linhas={6} />}>
      <Ativos />
    </Suspense>
  );
}
