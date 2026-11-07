"use client";

import { useMutation } from "@tanstack/react-query";
import { CalendarPlus, Check, FileSpreadsheet, MessageSquare, Undo2, UserRound } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { useAvisar } from "@/components/avisos";
import { Calendario } from "@/components/calendario";
import { FormEntrega } from "@/components/entrega";
import { FiltroMulti } from "@/components/filtro";
import { HistoricoDaObrigacao } from "@/components/historico";
import {
  AreaTexto, Botao, Campo, CampoEntrada, CampoSelecao, Carregando, Cartao, Entrada, ErroCarga, Secao, Selo, Titulo, Vazio, cx, mensagem,
} from "@/components/ui";
import { useQuery } from "@tanstack/react-query";
import { api, baixar, dados, type Consulta } from "@/lib/api";
import { type Linha, useAreas, useAtivos, useInvalidarTorre, usePainel } from "@/lib/consultas";
import { curto, dataBR, maiuscula, nomeDeArquivo, plural, somarDias } from "@/lib/formato";
import { ATRASADA, DADO_FALTANDO, ROTULO, TODOS, VENCE_LOGO, ordenar } from "@/lib/status";
import { useEmpresa, useTorre } from "@/lib/torre";

const PADRAO = [ATRASADA, DADO_FALTANDO, VENCE_LOGO];
const SEM_RESPONSAVEL = "";
const JANELAS = [7, 30, 90, 365];

type Filtros = { status: string[]; ativo: string[]; norma: string[]; responsavel: string[]; busca: string; vence: number | null };

function lerFiltros(p: URLSearchParams): Filtros {
  const status = p.getAll("status");
  return {
    // sem status na URL: o padrão (o que pede ação); "todos" limpa
    status: !p.has("status") ? PADRAO : status.filter((s) => s !== "todos"),
    ativo: p.getAll("ativo"),
    norma: p.getAll("norma"),
    responsavel: p.getAll("responsavel"),
    busca: p.get("busca") ?? "",
    vence: Number(p.get("vence")) || null,
  };
}

function escreverFiltros(f: Filtros): string {
  const p = new URLSearchParams();
  if (!f.status.length) p.append("status", "todos");
  else if (f.status.join() !== PADRAO.join()) f.status.forEach((s) => p.append("status", s));
  f.ativo.forEach((x) => p.append("ativo", x));
  f.norma.forEach((x) => p.append("norma", x));
  f.responsavel.forEach((x) => p.append("responsavel", x));
  if (f.busca) p.set("busca", f.busca);
  if (f.vence) p.set("vence", String(f.vence));
  const q = p.toString();
  return q ? `?${q}` : "";
}

function chave(l: Linha) {
  return `${l.ativo_id}|${l.codigo}`;
}

// ------------------------------------------------------------------ ações

function useAcoes() {
  const invalidar = useInvalidarTorre();
  const avisar = useAvisar();
  const executar = useMutation({
    mutationFn: async ({ linhas, faz }: { linhas: Linha[]; faz: (l: Linha) => Promise<unknown>; ok: string }) => {
      for (const l of linhas) await faz(l); // uma de cada vez: tudo vai para o histórico na ordem
    },
    onSuccess: (_, v) => { avisar(v.ok); invalidar(); },
    onError: (e) => { avisar(mensagem(e), "erro"); invalidar(); },
  });
  const atribuir = (linhas: Linha[], responsavel: string, ok: string) => executar.mutateAsync({
    linhas, ok, faz: (l) => dados(api.POST("/api/v1/atribuicoes", { body: { ativo_id: l.ativo_id!, codigo: l.codigo, responsavel } })),
  });
  const comentar = (linhas: Linha[], texto: string) => executar.mutateAsync({
    linhas, ok: linhas.length === 1 ? `Comentário registrado em ${linhas[0]!.ativo} · ${linhas[0]!.codigo}` : `Comentário registrado em ${linhas.length} obrigações`,
    faz: (l) => dados(api.POST("/api/v1/comentarios", { body: { ativo_id: l.ativo_id!, codigo: l.codigo, texto } })),
  });
  const entregar = (linhas: Linha[], dia: string) => executar.mutateAsync({
    linhas: linhas.filter((l) => l.agenda && l.agenda !== "evento"),
    ok: `${plural(linhas.filter((l) => l.agenda && l.agenda !== "evento").length, "entrega registrada", "entregas registradas")}`,
    faz: (l) => dados(api.POST("/api/v1/entregas", { body: { ativo_id: l.ativo_id!, codigo: l.codigo, dia } })),
  });
  const desfazer = (l: Linha, periodo: string, rotulo: string) => executar.mutateAsync({
    linhas: [l], ok: `Entrega de ${rotulo} desfeita`,
    faz: () => dados(api.DELETE("/api/v1/entregas", { params: { query: { ativo_id: l.ativo_id!, codigo: l.codigo, periodo } } })),
  });
  return { atribuir, comentar, entregar, desfazer, pendente: executar.isPending };
}

function EscolhaArea({ valor, onMudar, rotulo }: { valor: string; onMudar: (v: string) => void; rotulo: string }) {
  const areas = useAreas();
  const lista = areas.data?.areas ?? [];
  return (
    <Campo rotulo={rotulo} dica="Uma área da empresa, uma pessoa ou uma consultoria.">
      <Entrada list="areas-da-empresa" value={valor} onChange={(e) => onMudar(e.target.value)} placeholder="nome, área ou consultoria" aria-label={rotulo} />
      <datalist id="areas-da-empresa">{lista.map((a) => <option key={a} value={a} />)}</datalist>
    </Campo>
  );
}

function Varias({ linhas, onFeito }: { linhas: Linha[]; onFeito: () => void }) {
  const t = useTorre();
  const acoes = useAcoes();
  const [para, setPara] = useState("");
  const [dia, setDia] = useState(t.hoje);
  const [texto, setTexto] = useState("");
  const comAgenda = linhas.filter((l) => l.agenda && l.agenda !== "evento").length;
  return (
    <Cartao className="p-4" data-testid="acoes-varias">
      <p className="text-sm font-semibold">{linhas.length} obrigações selecionadas</p>
      <div className="mt-3 grid gap-5 md:grid-cols-3">
        <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); await acoes.entregar(linhas, dia); onFeito(); }}>
          <p className="text-[13px] font-semibold">Registrar entrega</p>
          <CampoEntrada rotulo="Entregues em" type="date" value={dia} max={t.hoje} onChange={(e) => setDia(e.target.value)}
            dica={`Cada uma no período que está pendente.${comAgenda < linhas.length ? ` ${linhas.length - comAgenda} por gatilho ficam de fora.` : ""}`} />
          <Botao type="submit" variante="primario" icone={<Check className="size-4" />} disabled={!comAgenda} carregando={acoes.pendente}>
            Marcar {comAgenda === 1 ? "como entregue" : `as ${comAgenda} como entregues`}
          </Botao>
        </form>
        <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); await acoes.atribuir(linhas, para.trim(), `${linhas.length} obrigações agora com ${para.trim()}`); setPara(""); onFeito(); }}>
          <p className="text-[13px] font-semibold">Passar para outra área</p>
          <EscolhaArea rotulo="Passar todas para" valor={para} onMudar={setPara} />
          <Botao type="submit" icone={<UserRound className="size-4" />} disabled={!para.trim()} carregando={acoes.pendente}>Atribuir responsável</Botao>
        </form>
        <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); await acoes.comentar(linhas, texto.trim()); setTexto(""); onFeito(); }}>
          <p className="text-[13px] font-semibold">Comentar</p>
          <Campo rotulo="Comentário em todas">
            <AreaTexto value={texto} onChange={(e) => setTexto(e.target.value)} rows={2} placeholder="ex.: laudos com a consultoria, chegam dia 20" aria-label="Comentário em todas" />
          </Campo>
          <Botao type="submit" icone={<MessageSquare className="size-4" />} disabled={!texto.trim()} carregando={acoes.pendente}>Comentar</Botao>
        </form>
      </div>
    </Cartao>
  );
}

function Uma({ l, onFeito }: { l: Linha; onFeito: () => void }) {
  const t = useTorre();
  const acoes = useAcoes();
  const [para, setPara] = useState("");
  const [texto, setTexto] = useState("");
  const [desfazer, setDesfazer] = useState("");
  const hist = useQuery({
    queryKey: [...t.chave, "historico", l.ativo_id, l.codigo],
    queryFn: () => dados(api.GET("/api/v1/ativos/{ativo_id}/obrigacoes/{codigo}/historico", { params: { path: { ativo_id: l.ativo_id!, codigo: l.codigo } } })),
  });
  const manuais = (hist.data?.evidencias ?? []).filter((e) => e.baixa_manual);
  const escolhidaDesfazer = manuais.find((e) => e.periodo === desfazer) ?? manuais[0];

  return (
    <Cartao className="p-4" data-testid="acoes-uma">
      <div className="flex flex-wrap items-center gap-2">
        <Selo status={l.status} />
        <h2 className="text-base font-semibold">{l.ativo} · {l.titulo}</h2>
      </div>
      <p className="mt-1 text-[13px] text-texto-2">{l.dispositivo} · {l.periodicidade ?? l.agenda_descricao} · evidência: {l.evidencia ?? "—"}</p>
      {l.nota && <p className="mt-1 text-sm">{maiuscula(l.nota)}.</p>}
      {l.trecho && <blockquote className="mt-2 border-l-2 border-borda-forte pl-3 text-[13px] italic text-texto-2">“{curto(l.trecho, 400)}”</blockquote>}

      {!t.soLeitura && <div className="mt-4 grid gap-5 md:grid-cols-3">
        <div>
          <p className="mb-2 text-[13px] font-semibold">Registrar entrega</p>
          {l.dados_faltando.some((c) => c !== "ultima_execucao") ? (
            <p className="text-sm text-texto-2">Falta no cadastro: {l.dados_faltando_rotulos.join("; ")}. Complete na ficha do ativo antes.</p>
          ) : <FormEntrega key={chave(l)} alvo={l} onFeito={onFeito} />}
        </div>
        <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); await acoes.atribuir([l], para.trim(), `${l.ativo} · ${l.codigo} agora com ${para.trim()}`); setPara(""); }}>
          <p className="text-[13px] font-semibold">Responsável</p>
          <p className="text-xs text-texto-2">
            Hoje: {l.responsavel ?? "ninguém"}{l.responsavel_proprio ? " (só desta obrigação)" : l.responsavel ? " (o do ativo)" : ""}
          </p>
          <EscolhaArea rotulo="Passar para" valor={para} onMudar={setPara} />
          <div className="flex flex-wrap gap-2">
            <Botao type="submit" icone={<UserRound className="size-4" />} disabled={!para.trim()} carregando={acoes.pendente}>Atribuir</Botao>
            {l.responsavel_proprio && (
              <Botao onClick={() => acoes.atribuir([l], "", `${l.ativo} · ${l.codigo} voltou ao responsável do ativo`)}>Voltar ao do ativo</Botao>
            )}
          </div>
        </form>
        <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); await acoes.comentar([l], texto.trim()); setTexto(""); }}>
          <p className="text-[13px] font-semibold">Comentário</p>
          <AreaTexto value={texto} onChange={(e) => setTexto(e.target.value)} rows={3} placeholder="ex.: laudo com a consultoria, chega dia 20" aria-label="Comentário" />
          <Botao type="submit" icone={<MessageSquare className="size-4" />} disabled={!texto.trim()} carregando={acoes.pendente}>Comentar</Botao>
        </form>
      </div>}

      <div className="mt-5 border-t border-borda pt-4">
        <p className="mb-3 text-[13px] font-semibold">Histórico</p>
        <HistoricoDaObrigacao ativoId={l.ativo_id!} codigo={l.codigo} />
        {!t.soLeitura && manuais.length > 0 && escolhidaDesfazer && (
          <div className="mt-4 flex flex-wrap items-end gap-2">
            <CampoSelecao rotulo="Desfazer uma entrega manual" value={escolhidaDesfazer.periodo} onChange={(e) => setDesfazer(e.target.value)} className="w-64">
              {manuais.map((e) => <option key={e.id} value={e.periodo}>{e.periodo_rotulo}</option>)}
            </CampoSelecao>
            <Botao variante="perigo" icone={<Undo2 className="size-4" />} carregando={acoes.pendente}
              onClick={() => acoes.desfazer(l, escolhidaDesfazer.periodo, escolhidaDesfazer.periodo_rotulo)}>
              Desfazer
            </Botao>
          </div>
        )}
      </div>
    </Cartao>
  );
}

// ------------------------------------------------------------------ tela

function Entregas() {
  const t = useTorre();
  const empresa = useEmpresa();
  const avisar = useAvisar();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const painel = usePainel();
  const ativos = useAtivos();
  const f = useMemo(() => lerFiltros(new URLSearchParams(params.toString())), [params]);
  const [busca, setBusca] = useState(f.busca);
  const [sel, setSel] = useState<Set<string>>(new Set());

  const mudar = (novo: Partial<Filtros>) => {
    router.replace(`${caminho}${escreverFiltros({ ...f, ...novo })}`, { scroll: false });
    setSel(new Set());
  };

  const todas = useMemo(() => painel.data?.linhas ?? [], [painel.data]);
  const limite = f.vence ? somarDias(t.hoje, f.vence) : null;
  const termo = f.busca.trim().toLowerCase();
  const filtradas = useMemo(() => ordenar(todas.filter((l) =>
    (!f.status.length || f.status.includes(l.status)) && (!f.ativo.length || f.ativo.includes(l.ativo))
    && (!f.norma.length || (l.norma && f.norma.includes(l.norma)))
    && (!f.responsavel.length || f.responsavel.includes(l.responsavel ?? SEM_RESPONSAVEL))
    && (!termo || `${l.titulo} ${l.codigo} ${l.norma} ${l.evidencia}`.toLowerCase().includes(termo))
    && (!limite || (!!l.vence && l.vence <= limite)))), [todas, f, termo, limite]);
  const escolhidas = filtradas.filter((l) => sel.has(chave(l)));

  const opNorma = [...new Set(todas.map((l) => l.norma).filter((n): n is string => !!n))].sort().map((n) => ({ valor: n, rotulo: n }));
  const opResp = [...new Set(todas.map((l) => l.responsavel ?? SEM_RESPONSAVEL))].sort()
    .map((r) => ({ valor: r, rotulo: r || "— sem responsável" }));
  const opAtivo = (ativos.data ?? []).map((a) => ({ valor: a.codigo, rotulo: `${a.codigo} · ${a.nome}` }));

  const consulta: Consulta = {
    hoje: t.hoje, status: f.status, ativo: f.ativo, norma: f.norma, responsavel: f.responsavel, busca: f.busca, vence_ate: limite,
  };
  const nomeArq = `obrigacoes_${nomeDeArquivo(t.veTudo ? "diretoria" : t.eu.area ?? t.eu.visao)}_${t.hoje}`;
  const baixe = (caminhoApi: string, c: Consulta, nome: string) => baixar(caminhoApi, c, nome).catch((e) => avisar(mensagem(e), "erro"));
  const alternar = (k: string) => setSel((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const todasMarcadas = filtradas.length > 0 && filtradas.every((l) => sel.has(chave(l)));

  return (
    <>
      <Titulo titulo="Entregas" />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FiltroMulti rotulo="Status" valor={f.status} onMudar={(v) => mudar({ status: v })}
          opcoes={TODOS.map((s) => ({ valor: s, rotulo: ROTULO[s]! }))} />
        <FiltroMulti rotulo="Ativo" valor={f.ativo} onMudar={(v) => mudar({ ativo: v })} opcoes={opAtivo} />
        <FiltroMulti rotulo="Norma" valor={f.norma} onMudar={(v) => mudar({ norma: v })} opcoes={opNorma} todos="todas" />
        <FiltroMulti rotulo="Responsável" valor={f.responsavel} onMudar={(v) => mudar({ responsavel: v })} opcoes={opResp} />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-[2fr_1fr]">
        <form onSubmit={(e) => { e.preventDefault(); mudar({ busca: busca.trim() }); }}>
          <CampoEntrada rotulo="Buscar na obrigação" type="search" value={busca} placeholder="ex.: FIR, RPSB, simulado, NR-13…"
            onChange={(e) => setBusca(e.target.value)} onBlur={() => busca.trim() !== f.busca && mudar({ busca: busca.trim() })} />
        </form>
        <CampoSelecao rotulo="Vence em" value={f.vence ?? ""} onChange={(e) => mudar({ vence: Number(e.target.value) || null })}>
          <option value="">qualquer data</option>
          {JANELAS.map((d) => <option key={d} value={d}>até {d} dias</option>)}
        </CampoSelecao>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Botao tamanho="p" icone={<FileSpreadsheet className="size-3.5" />} disabled={!filtradas.length}
          onClick={() => baixe(`/api/v1/empresas/${empresa.id}/planilha`, consulta, `${nomeArq}.xlsx`)}>
          Excel ({plural(filtradas.length, "linha", "linhas")})
        </Botao>
        <Botao tamanho="p" icone={<CalendarPlus className="size-3.5" />} title="Os vencimentos de quem está olhando, para o Outlook ou Google Agenda"
          onClick={() => baixe(`/api/v1/empresas/${empresa.id}/calendario.ics`, { hoje: t.hoje }, `vencimentos_${nomeArq}.ics`)}>
          Agenda (.ics)
        </Botao>
        <p className="text-xs text-texto-2" data-testid="contagem-entregas">
          {filtradas.length} de {plural(todas.length, "obrigação", "obrigações")}.
          {escolhidas.length > 0 && ` ${escolhidas.length} selecionada${escolhidas.length > 1 ? "s" : ""}.`}
        </p>
      </div>

      {painel.error && <ErroCarga erro={painel.error} onTentar={() => painel.refetch()} />}
      {painel.isLoading ? <Carregando linhas={8} className="mt-3" /> : (
        <div className="mt-3 max-h-[480px] overflow-auto rounded-lg border border-borda">
          <table className="w-full min-w-[880px] text-sm" data-testid="tabela-entregas">
            <thead className="sticky top-0 z-10 bg-fundo-2 text-left text-xs text-texto-2">
              <tr>
                <th className="w-9 px-3 py-2">
                  <input type="checkbox" aria-label="Selecionar todas" checked={todasMarcadas} disabled={!filtradas.length}
                    onChange={() => setSel(todasMarcadas ? new Set() : new Set(filtradas.map(chave)))} className="size-4 accent-[var(--marca)]" />
                </th>
                {["Status", "Ativo", "Obrigação", "Vence", "Responsável", "Última", "Pendente"].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-borda">
              {filtradas.map((l) => {
                const k = chave(l);
                return (
                  <tr key={k} onClick={() => alternar(k)} aria-selected={sel.has(k)}
                    className={cx("cursor-pointer", sel.has(k) ? "bg-marca-suave" : "hover:bg-fundo-2")}>
                    <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={sel.has(k)} onChange={() => alternar(k)} aria-label={`Selecionar ${l.ativo} · ${l.codigo}`}
                        className="size-4 accent-[var(--marca)]" />
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap"><Selo status={l.status} /></td>
                    <td className="px-3 py-2 font-medium">{l.ativo}</td>
                    <td className="px-3 py-2">{curto(l.titulo, 90)}</td>
                    <td className="num px-3 py-2 whitespace-nowrap">{l.vence ? dataBR(l.vence) : ""}</td>
                    <td className="px-3 py-2 text-texto-2">{l.responsavel ?? "—"}{l.responsavel_proprio && <span title="responsável só desta obrigação"> ✎</span>}</td>
                    <td className="px-3 py-2 text-texto-2">{l.ultima_rotulo ?? ""}</td>
                    <td className="px-3 py-2 text-texto-2">{l.pendente}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!filtradas.length && <div className="p-4"><Vazio>Nenhuma obrigação com esses filtros.</Vazio></div>}
        </div>
      )}

      <div className="mt-4">
        {escolhidas.length > 1 && !t.soLeitura && <Varias linhas={escolhidas} onFeito={() => setSel(new Set())} />}
        {escolhidas.length === 1 && <Uma key={chave(escolhidas[0]!)} l={escolhidas[0]!} onFeito={() => setSel(new Set())} />}
      </div>

      <Secao titulo="Calendário do mês" className="mt-10">
        <Calendario ativos={f.ativo} />
      </Secao>
    </>
  );
}

export default function PaginaEntregas() {
  return (
    <Suspense fallback={<Carregando linhas={8} />}>
      <Entregas />
    </Suspense>
  );
}
