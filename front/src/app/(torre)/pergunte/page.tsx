"use client";

import { CircleAlert, RotateCcw, SendHorizontal, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/markdown";
import { AreaTexto, Aviso, Botao, Carregando, Cartao, Etiqueta, Titulo, cx, mensagem } from "@/components/ui";
import { useEstadoPergunta, usePerguntar } from "@/lib/consultas";
import { type MensagemChat, type RespostaPergunta, SUGESTOES, consultas, historicoPara, resumoConferencia } from "@/lib/pergunta";

function Conferencia({ r }: { r: RespostaPergunta }) {
  const c = resumoConferencia(r.conferencia);
  return (
    <div className="mt-3 space-y-1.5" data-testid="conferencia" data-ok={c.ok}>
      <p className={cx("flex items-center gap-1.5 text-xs font-medium", c.ok ? "text-emdia" : "text-atrasada")}>
        {c.ok ? <ShieldCheck className="size-3.5" aria-hidden /> : <CircleAlert className="size-3.5" aria-hidden />}
        {c.texto}
      </p>
      {!c.ok && (
        <ul className="list-disc pl-5 text-xs text-atrasada">{c.fora.map((f) => <li key={f}>{f}</li>)}</ul>
      )}
    </div>
  );
}

function Resposta({ r }: { r: RespostaPergunta }) {
  const vistas = consultas(r);
  return (
    <Cartao className="p-4 sm:p-5" data-testid="resposta">
      <Markdown texto={r.texto} />
      <Conferencia r={r} />
      <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-borda pt-3 text-xs text-texto-3">
        {vistas.length > 0 ? (
          <>
            <span>Consultou:</span>
            {vistas.map((v) => <Etiqueta key={v}>{v}</Etiqueta>)}
          </>
        ) : <span>Respondeu sem consultar a torre.</span>}
        <span className="ml-auto" title={`${r.tokens_in} tokens de entrada (${r.tokens_cache} do cache), ${r.tokens_out} de saída`}>
          {r.modelo.split(":").pop()} · {r.segundos.toFixed(0)} s · US$ {r.custo_usd.toFixed(4)}
        </span>
      </div>
    </Cartao>
  );
}

function Mensagem({ m }: { m: MensagemChat }) {
  if (m.papel === "usuario") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-marca px-4 py-2.5 text-sm text-sobre-marca" data-testid="pergunta">
          {m.texto}
        </p>
      </div>
    );
  }
  if (m.papel === "erro") return <Aviso tipo="erro">{m.texto}</Aviso>;
  return <Resposta r={m.resposta} />;
}

export default function Pergunte() {
  const estado = useEstadoPergunta();
  const perguntar = usePerguntar();
  const [msgs, setMsgs] = useState<MensagemChat[]>([]);
  const [texto, setTexto] = useState("");
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, perguntar.isPending]);

  function enviar(pergunta: string) {
    const p = pergunta.trim();
    if (!p || perguntar.isPending) return;
    const historico = historicoPara(msgs);
    setMsgs((atual) => [...atual, { papel: "usuario", texto: p }]);
    setTexto("");
    perguntar.mutate({ pergunta: p, historico }, {
      onSuccess: (r) => setMsgs((atual) => [...atual, { papel: "torre", texto: r.texto, resposta: r }]),
      onError: (e) => setMsgs((atual) => [...atual, { papel: "erro", texto: mensagem(e) }]),
    });
  }

  const desligada = estado.data && !estado.data.ligada;
  return (
    <div className="flex min-h-[calc(100dvh-2.5rem)] flex-col lg:min-h-[calc(100dvh-4rem)]">
      <Titulo titulo="Assistente Mitra" acoes={msgs.length > 0 && (
        <Botao tamanho="p" icone={<RotateCcw className="size-3.5" />} onClick={() => setMsgs([])} disabled={perguntar.isPending}>
          Nova conversa
        </Botao>
      )} />

      {desligada && (
        <Aviso tipo="atencao" className="mb-4">
          Funcionalidade desativada neste ambiente, pois nenhum provedor de IA está configurado.
        </Aviso>
      )}

      <div className="flex flex-1 flex-col" data-testid="conversa">
        <div className="space-y-4">
          {msgs.length === 0 && (
            <Cartao className="mx-auto max-w-3xl bg-transparent p-6 text-center shadow-none">
              <p className="flex items-center justify-center gap-2 text-base font-semibold"><Sparkles className="size-4 text-marca" aria-hidden />Experimente</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {SUGESTOES.map((s) => (
                  <button key={s} type="button" onClick={() => enviar(s)} disabled={!!desligada || perguntar.isPending}
                    className="rounded-full border border-borda bg-transparent px-3 py-1.5 text-left text-[13px] text-texto-2 transition-colors hover:border-marca hover:text-marca disabled:opacity-50"
                    data-testid="sugestao">
                    {s}
                  </button>
                ))}
              </div>
            </Cartao>
          )}

          {msgs.map((m, i) => <Mensagem key={i} m={m} />)}

          {perguntar.isPending && (
            <Cartao className="p-4" aria-live="polite">
              <p className="mb-2 text-xs text-texto-3">Consultando a torre…</p>
              <Carregando linhas={3} />
            </Cartao>
          )}
          <div ref={fim} />
        </div>

        <form className="mt-auto flex items-end gap-2 rounded-xl border border-borda bg-fundo-2 p-2 shadow-sm"
          onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
          <label htmlFor="pergunta" className="sr-only">Sua pergunta</label>
          <AreaTexto id="pergunta" rows={2} value={texto} maxLength={2000} disabled={!!desligada}
            placeholder="Ex.: o que vence nos próximos 30 dias na B2?" className="min-h-0 flex-1 resize-none border-0 bg-transparent shadow-none focus:ring-0"
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(texto); }
            }} />
          <Botao type="submit" variante="primario" carregando={perguntar.isPending} disabled={!texto.trim() || !!desligada}
            icone={<SendHorizontal className="size-4" />}>
            Perguntar
          </Botao>
        </form>
      </div>
    </div>
  );
}
