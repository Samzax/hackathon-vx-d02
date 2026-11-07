"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Send, ShieldAlert, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useAvisar } from "@/components/avisos";
import { AreaTexto, Aviso, Botao, Carregando, Cartao, Campo, ErroCarga, Etiqueta, Numero, Secao, Titulo, mensagem } from "@/components/ui";
import { api, dados, type Esquemas } from "@/lib/api";
import { useInvalidarTorre, useRadar } from "@/lib/consultas";
import { numero, plural, usd } from "@/lib/formato";
import { useTorre } from "@/lib/torre";

type Analise = Esquemas["AnaliseAto"];

const TAREFA: Record<string, string> = { impacto: "análise de impacto de atos", extrator: "extração de obrigações de normas" };
const GUARDA = "mitra_analise_teste";

function Funil({ f }: { f: Esquemas["Funil"] }) {
  const passos = [
    { valor: numero(f.atos), rotulo: `Atos no DOU (${f.mes})` },
    { valor: numero(f.anm), rotulo: "Da ANM" },
    { valor: numero(f.normativos), rotulo: "Normativos da ANM → IA" },
    { valor: numero(f.mudam), rotulo: "Mudam o cadastro" },
  ];
  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="funil">
        {passos.map((p) => <Numero key={p.rotulo} valor={p.valor} rotulo={p.rotulo} />)}
      </div>
      <p className="mt-2 text-xs text-texto-2">
        Filtro por órgão e tipo de ato é regra, sem custo. Só os normativos chegam à IA, e só com as obrigações que a triagem
        considerou candidatas. Fonte: {f.fonte}.
      </p>
    </>
  );
}

function ResultadoAnalise({ an, texto, onEnviado }: { an: Analise; texto: string; onEnviado: () => void }) {
  const t = useTorre();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const propor = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/radar/propor", { body: { texto } })),
    onSuccess: () => { avisar("Mudança proposta: aprove ou rejeite em Regulatório → Mudanças."); invalidar(); onEnviado(); },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  return (
    <Cartao className="mt-4 p-4" data-testid="analise">
      <p className="font-semibold">{an.ato_nome ?? an.ato}</p>
      {an.candidatas.length > 0 ? (
        <>
          <p className="mt-2 text-[13px] text-texto-2">Candidatas escolhidas pela regra (sem custo):</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {an.candidatas.map((c) => (
              <li key={c.codigo} title={c.titulo ?? undefined}>
                <Etiqueta tom="neutro"><code>{c.codigo}</code>&nbsp;<span className="font-normal">({c.motivos.slice(0, 2).join(", ")})</span></Etiqueta>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm">{an.motivo || "—"}</p>
        </>
      ) : (
        <Aviso tipo="info" className="mt-2">Nenhuma obrigação do cadastro é tocada por este ato: a IA nem foi chamada (custo zero).</Aviso>
      )}
      {an.modelos.length > 0 && (
        <p className="mt-2 text-xs text-texto-2">
          Modelo: {an.modelos.join(" → ")} · custo da análise {usd(an.custo_original_usd)}
          {an.custo_original_usd > 0 && !an.custo_usd && " (resposta já em cache: não foi paga de novo)"}
        </p>
      )}
      {an.mudancas.length > 0 && (
        <ul className="mt-3 space-y-3">
          {an.mudancas.map((m, i) => (
            <li key={i} className="text-sm">
              <p className="flex flex-wrap items-center gap-2">
                <strong>{m.obrigacao}</strong> · {m.campo_rotulo}: {m.valor_atual_texto} → <strong>{m.valor_novo_texto}</strong>
                {m.reprovada
                  ? <Etiqueta tom="perigo"><ShieldAlert className="mr-1 size-3" />reprovada pelo Python: {m.reprovada}</Etiqueta>
                  : <Etiqueta tom="ok"><ShieldCheck className="mr-1 size-3" />conferida pelo Python</Etiqueta>}
              </p>
              <blockquote className="mt-1 border-l-2 border-borda-forte pl-3 text-[13px] italic text-texto-2">“{m.trecho}”</blockquote>
            </li>
          ))}
        </ul>
      )}
      {an.aprovadas > 0 && (t.plataforma ? (
        <Botao className="mt-4" variante="primario" icone={<Send className="size-4" />} carregando={propor.isPending} onClick={() => propor.mutate()}>
          Enviar para aprovação (Mudanças)
        </Botao>
      ) : (
        <Aviso tipo="info" className="mt-4">
          {plural(an.aprovadas, "mudança passou", "mudanças passaram")} na conferência. Quem transforma isso em proposta é a curadoria da
          Mitra: a norma é pública e vale para todas as clientes. Aqui é só o teste: nada foi gravado.
        </Aviso>
      ))}
    </Cartao>
  );
}

type Feita = { texto: string; an: Analise };

/** O texto colado e a análise ficam na aba (sessionStorage): a análise de teste não é gravada na API. */
function TesteComAto() {
  const avisar = useAvisar();
  const qc = useQueryClient();
  const [texto, setTexto] = useState("");
  const [feita, setFeita] = useState<Feita | null>(null);

  useEffect(() => {
    try {
      const g = JSON.parse(sessionStorage.getItem(GUARDA) ?? "{}") as { texto?: string; feita?: Feita };
      // eslint-disable-next-line react-hooks/set-state-in-effect -- só lê o que a aba guardou, uma vez
      if (g.texto) setTexto(g.texto);
      if (g.feita) setFeita(g.feita);
    } catch { /* nada guardado */ }
  }, []);
  const guardar = (t: string, f: Feita | null) => {
    try { sessionStorage.setItem(GUARDA, JSON.stringify({ texto: t, feita: f })); } catch { /* sem armazenamento */ }
  };

  const exemplo = useMutation({
    mutationFn: () => dados(api.GET("/api/v1/radar/exemplo")),
    onSuccess: (x) => { setTexto(x.texto); setFeita(null); guardar(x.texto, null); },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  const analisar = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/radar/analise", { body: { texto } })),
    onSuccess: (an) => {
      const f = { texto, an };
      setFeita(f);
      guardar(texto, f);
      void qc.invalidateQueries({ predicate: (q) => q.queryKey.includes("radar") }); // o gasto de hoje mudou
    },
  });

  return (
    <Secao titulo="Teste com um ato seu" id="teste" className="mt-10"
      descricao="Cole o texto de um ato. A regra escolhe as obrigações candidatas sem custo; a IA só roda se houver candidata; o Python confere o que ela disser; nada muda sem aprovação.">
      <div className="space-y-3">
        <Botao tamanho="p" icone={<FlaskConical className="size-3.5" />} carregando={exemplo.isPending} onClick={() => exemplo.mutate()}>
          Usar um ato fictício de exemplo
        </Botao>
        <Campo rotulo="Texto do ato">
          <AreaTexto value={texto} onChange={(e) => setTexto(e.target.value)} rows={8} aria-label="Texto do ato"
            placeholder="Cole aqui o texto de uma resolução, portaria, instrução normativa…" className="font-mono text-[13px]" />
        </Campo>
        <Botao variante="primario" disabled={!texto.trim()} carregando={analisar.isPending} onClick={() => analisar.mutate()}>
          Analisar ato
        </Botao>
        {analisar.isPending && <p className="text-[13px] text-texto-2">Triagem por regra e, se houver candidata, análise da IA…</p>}
        {analisar.error && <Aviso tipo="erro">{mensagem(analisar.error)}.</Aviso>}
      </div>
      {feita && <ResultadoAnalise an={feita.an} texto={feita.texto} onEnviado={() => { setFeita(null); guardar(texto, null); }} />}
    </Secao>
  );
}

export default function Radar() {
  const radar = useRadar();
  const r = radar.data;
  return (
    <>
      <Titulo sobre="Regulatório" titulo="Radar do DOU">
        Todo dia o radar lê o Diário Oficial: regra primeiro, IA só no que sobra, Python conferindo, pessoa aprovando.
      </Titulo>
      {radar.isLoading && <Carregando linhas={4} />}
      {radar.error && <ErroCarga erro={radar.error} onTentar={() => radar.refetch()} />}
      {r && (
        <>
          {r.funil ? <Funil f={r.funil} /> : <Aviso tipo="info">O funil do mês ainda não foi medido.</Aviso>}

          <Secao titulo="Custo real de IA até agora" className="mt-8"
            descricao="Cada resposta fica em cache e não é paga de novo: a mesma pergunta nunca custa duas vezes.">
            {r.custo_ia.length ? (
              <ul className="grid gap-3 sm:grid-cols-2">
                {r.custo_ia.map((g) => (
                  <li key={g.tarefa}><Numero valor={usd(g.usd, 3)} rotulo={TAREFA[g.tarefa] ?? g.tarefa} dica={plural(g.n, "chamada", "chamadas")} /></li>
                ))}
              </ul>
            ) : <p className="text-sm text-texto-2">Nenhuma chamada de IA registrada ainda.</p>}
            <p className="mt-2 text-xs text-texto-3">
              {r.ia.ligada ? `IA ligada · gasto hoje ${usd(r.ia.gasto_hoje_usd, 4)}${r.ia.teto_dia_usd ? ` de ${usd(r.ia.teto_dia_usd, 2)} por dia` : ""}.` : "IA desligada: só regra e respostas em cache."}
            </p>
          </Secao>

          <Secao titulo="Atos analisados" className="mt-8">
            <ul className="space-y-3">
              {r.analises.map((a) => {
                const mudam = [...new Set(a.mudancas.filter((x) => !x.reprovada).map((x) => x.obrigacao))].sort();
                return (
                  <li key={a.ato}>
                    <Cartao className="p-4">
                      <p className="text-sm">
                        <strong>{a.ato_nome ?? a.ato}</strong> — {mudam.length ? <span className="font-semibold text-proposta">muda {mudam.join(", ")}</span> : "não muda o cadastro"}
                      </p>
                      <p className="mt-1 text-[13px] text-texto-2">{a.motivo}</p>
                      <p className="mt-1 text-xs text-texto-3">
                        Obrigações enviadas à IA: {a.candidatas.join(", ") || "nenhuma"} · modelo: {a.modelos.join(" → ")}
                        {a.confianca !== null && ` · confiança ${String(a.confianca).replace(".", ",")}`} · custo {usd(a.custo_original_usd)}
                        {!a.custo_usd && a.custo_original_usd > 0 && " (resposta já em cache: não foi paga de novo)"}
                      </p>
                    </Cartao>
                  </li>
                );
              })}
            </ul>
            {!r.analises.length && <p className="text-sm text-texto-2">Nenhum ato analisado ainda.</p>}
          </Secao>
        </>
      )}
      <TesteComAto />
    </>
  );
}
