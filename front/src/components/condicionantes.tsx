"use client";

// A condicionante que a IA propôs a partir do PDF da licença: o trecho literal que a sustenta (e a página
// dele no PDF) e a decisão de quem é da empresa — aprovar, corrigir e aprovar, ou rejeitar. Quando a API
// diz que quem está olhando não decide (a plataforma só lê), os botões não aparecem: aparece quem decide.
import { useMutation } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { useState } from "react";
import { useAvisar } from "@/components/avisos";
import { Aviso, Botao, CampoEntrada, Cartao, Etiqueta, Expansivel, mensagem } from "@/components/ui";
import { api, dados, type Esquemas } from "@/lib/api";
import { useInvalidarTorre } from "@/lib/consultas";
import { emBrasilia } from "@/lib/formato";
import { useEmpresa } from "@/lib/torre";

export type Condicionante = Esquemas["Condicionante"];
export type Decisao = { status: string; codigo: string | null };

const TOM: Record<string, "proposta" | "ok" | "perigo"> = {
  pendente: "proposta", aprovada: "ok", rejeitada: "perigo",
};
const ROTULO: Record<string, string> = {
  pendente: "aguardando decisão", aprovada: "aprovada", rejeitada: "rejeitada",
};
const APLICA: Record<string, string> = { empresa: "a empresa", unidade: "a unidade", ativo: "o ativo" };

/** O que quem aprova pode corrigir antes: os cinco campos que mudam a cobrança na torre. */
const CAMPOS = [
  { campo: "titulo", rotulo: "Título", dica: "a obrigação em uma frase, no imperativo" },
  { campo: "prazo", rotulo: "Prazo", dica: "como a licença diz (ex.: até 30 dias após o fim do trimestre)" },
  { campo: "periodicidade", rotulo: "Periodicidade", dica: "mensal, trimestral, semestral, anual, por evento…" },
  { campo: "agenda", rotulo: "Agenda da torre", dica: "ex.: trimestral+30d, anual+30d, anos:2, meses:6, unica, evento" },
  { campo: "evidencia", rotulo: "Evidência", dica: "o documento que comprova a execução" },
] as const;
type Campo = (typeof CAMPOS)[number]["campo"];

function comoVeio(c: Condicionante): Record<Campo, string> {
  return {
    titulo: c.titulo,
    prazo: c.prazo ?? "",
    periodicidade: c.periodicidade ?? "",
    agenda: c.agenda ?? "",
    evidencia: c.evidencia ?? "",
  };
}

export function CartaoCondicionante({ c, onDecidida }: {
  c: Condicionante;
  onDecidida?: (c: Condicionante, decisao: Decisao) => void;
}) {
  const empresa = useEmpresa();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const original = comoVeio(c);
  const [valores, setValores] = useState<Record<Campo, string>>(() => comoVeio(c));

  const decidir = useMutation({
    mutationFn: ({ aprovar, correcoes }: { aprovar: boolean; correcoes?: Record<string, string | null> }) =>
      dados(api.POST("/api/v1/condicionantes/{condicionante_id}/decisao", {
        params: { path: { condicionante_id: c.id }, query: { empresa_id: empresa.id } },
        body: { aprovar, correcoes: correcoes ?? null },
      })),
    onSuccess: (r, pedido) => {
      avisar(pedido.aprovar
        ? (r.codigo ? `Aprovada: virou a obrigação ${r.codigo}.` : "Condicionante aprovada.")
        : "Condicionante rejeitada: não entra na torre.");
      onDecidida?.(c, r);
      return invalidar();
    },
    onError: (e) => avisar(`Decisão não aceita: ${mensagem(e)}`, "erro"),
  });

  const mudaram = CAMPOS.map((x) => x.campo).filter((k) => valores[k] !== original[k]);
  const correcoes = Object.fromEntries(mudaram.map((k) => [k, valores[k].trim() || null]));
  const podeCorrigir = mudaram.length > 0 && !!valores.titulo.trim();
  const decidindo = decidir.isPending;
  const quem = (c.decidida_por ?? "").split(" (")[0];

  return (
    <Cartao className="p-4 sm:p-5" data-testid="condicionante">
      <div className="flex flex-wrap items-center gap-2">
        <Etiqueta tom={TOM[c.status] ?? "neutro"}>{ROTULO[c.status] ?? c.status}</Etiqueta>
        <Etiqueta tom="marca">{c.licenca}</Etiqueta>
        {c.codigo && <Etiqueta tom="ok">{c.codigo}</Etiqueta>}
      </div>

      <h2 className="mt-2 text-base font-semibold">{c.titulo}</h2>

      <dl className="mt-2 grid gap-x-6 gap-y-1 text-[13px] sm:grid-cols-2">
        <div>
          <dt className="text-xs text-texto-3">Prazo</dt>
          <dd>{c.prazo ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-texto-3">Periodicidade</dt>
          <dd>{c.periodicidade ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-texto-3">Agenda da torre</dt>
          <dd className="num">{c.agenda ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-texto-3">Evidência</dt>
          <dd>{c.evidencia ?? "—"}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-texto-3">Aplica-se a</dt>
          <dd>{APLICA[c.aplica_a ?? ""] ?? c.aplica_a ?? "—"}{c.alvo ? ` · ${c.alvo}` : ""}</dd>
        </div>
      </dl>

      <figure className="mt-3">
        <figcaption className="mb-1 text-xs font-semibold uppercase tracking-wide text-texto-3">Trecho da licença</figcaption>
        <blockquote className="border-l-2 border-marca pl-3 text-sm italic">“{c.trecho}”</blockquote>
        {c.pagina != null && (
          <p className="mt-1 text-xs text-texto-3">página {c.pagina} do PDF</p>
        )}
      </figure>

      {c.codigo && (
        <p className="mt-3 text-sm">
          Virou a obrigação <strong>{c.codigo}</strong>, já vigente: a torre passa a cobrá-la.
        </p>
      )}

      {c.status !== "pendente" && (
        <p className="mt-1 text-[13px] text-texto-2">
          {c.status === "aprovada" ? "Aprovada" : "Rejeitada"} por {quem || "—"} em {emBrasilia(c.decidida_em)}.
        </p>
      )}

      {c.decide ? (
        <>
          <div className="mt-4 flex flex-wrap gap-2">
            <Botao variante="primario" icone={<Check className="size-4" aria-hidden />} disabled={decidindo}
              carregando={decidindo && decidir.variables?.aprovar === true && !decidir.variables?.correcoes}
              onClick={() => decidir.mutate({ aprovar: true })}>
              Aprovar
            </Botao>
            <Botao variante="perigo" icone={<X className="size-4" aria-hidden />} disabled={decidindo}
              onClick={() => decidir.mutate({ aprovar: false })}>
              Rejeitar
            </Botao>
          </div>
          <Expansivel className="mt-3" resumo={<span className="font-medium">Corrigir antes de aprovar</span>}>
            <p className="mb-3 text-[13px] text-texto-2">
              Se a leitura errou, corrija aqui: a obrigação nasce com o seu valor. A proposta original fica registrada na decisão.
            </p>
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); decidir.mutate({ aprovar: true, correcoes }); }}>
              <div className="grid gap-3 sm:grid-cols-2">
                {CAMPOS.map((x) => (
                  <CampoEntrada key={x.campo} rotulo={x.rotulo} dica={x.dica} value={valores[x.campo]}
                    onChange={(e) => setValores((v) => ({ ...v, [x.campo]: e.target.value }))} />
                ))}
              </div>
              <Botao type="submit" disabled={!podeCorrigir || decidindo} carregando={decidindo && !!decidir.variables?.correcoes}>
                Aprovar com correção
              </Botao>
            </form>
          </Expansivel>
        </>
      ) : c.status === "pendente" ? (
        <Aviso tipo="info" className="mt-4">
          Quem decide esta condicionante é <strong>{c.quem_decide}</strong>. Até lá ela não vira obrigação e a torre não cobra nada.
        </Aviso>
      ) : null}
    </Cartao>
  );
}
