"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarClock, FileCheck2, MessageSquare, Pencil, UserRound } from "lucide-react";
import { api, dados, type Esquemas } from "@/lib/api";
import { emBrasilia } from "@/lib/formato";
import { useTorre } from "@/lib/torre";
import { Carregando, ErroCarga, Vazio } from "./ui";

const TIPO_EVENTO: Record<string, { rotulo: string; icone: React.ReactNode }> = {
  entrega: { rotulo: "Entrega", icone: <FileCheck2 className="size-3.5 text-emdia" /> },
  entrega_desfeita: { rotulo: "Entrega desfeita", icone: <FileCheck2 className="size-3.5 text-atrasada" /> },
  comentario: { rotulo: "Comentário", icone: <MessageSquare className="size-3.5 text-marca" /> },
  responsavel: { rotulo: "Responsável", icone: <UserRound className="size-3.5 text-gatilho" /> },
  atribuicao: { rotulo: "Atribuição", icone: <UserRound className="size-3.5 text-gatilho" /> },
  cadastro: { rotulo: "Cadastro", icone: <Pencil className="size-3.5 text-faltando" /> },
};

export function Eventos({ eventos, vazio = "Nada registrado ainda." }: { eventos: Esquemas["Evento"][]; vazio?: string }) {
  if (!eventos.length) return <Vazio>{vazio}</Vazio>;
  return (
    <ol className="space-y-2.5">
      {eventos.map((e) => {
        const t = TIPO_EVENTO[e.tipo] ?? { rotulo: e.tipo, icone: <CalendarClock className="size-3.5 text-texto-3" /> };
        return (
          <li key={e.id} className="flex gap-2.5 text-sm">
            <span className="mt-0.5 shrink-0" aria-hidden>{t.icone}</span>
            <div className="min-w-0">
              <p>
                <span className="font-medium">{t.rotulo}</span>
                {e.codigo && <span className="text-texto-2"> · {e.codigo}</span>}
                {e.texto && <span>: {e.texto}</span>}
              </p>
              <p className="text-xs text-texto-3">{emBrasilia(e.em)}{e.por ? ` · ${e.por}` : ""}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function Evidencias({ evidencias, titulos }: { evidencias: Esquemas["Evidencia"][]; titulos?: Record<string, string> }) {
  if (!evidencias.length) return <Vazio>Nenhuma evidência registrada ainda.</Vazio>;
  return (
    <ul className="space-y-2.5">
      {evidencias.map((e) => (
        <li key={e.id} className="text-sm">
          <p>
            <strong>{e.periodo_rotulo}</strong> · {e.codigo}
            {titulos?.[e.codigo] && <span className="text-texto-2"> {titulos[e.codigo]}</span>}
          </p>
          <p className="text-xs text-texto-3">
            {e.arquivo_nome ?? "sem arquivo"} · {e.origem}{e.recebida_em ? ` · recebida ${emBrasilia(e.recebida_em)}` : ""}
          </p>
          {e.avisos.map((a) => <p key={a} className="text-xs text-vence">{a}</p>)}
        </li>
      ))}
    </ul>
  );
}

/** O que se fez numa obrigação de um ativo: entregas (com comprovante), comentários e atribuições. */
export function HistoricoDaObrigacao({ ativoId, codigo }: { ativoId: number; codigo: string }) {
  const t = useTorre();
  const h = useQuery({
    queryKey: [...t.chave, "historico", ativoId, codigo],
    queryFn: () => dados(api.GET("/api/v1/ativos/{ativo_id}/obrigacoes/{codigo}/historico", { params: { path: { ativo_id: ativoId, codigo } } })),
  });
  if (h.isLoading) return <Carregando linhas={2} />;
  if (h.error) return <ErroCarga erro={h.error} onTentar={() => h.refetch()} />;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-texto-3">Entregas</p>
        <Evidencias evidencias={h.data!.evidencias} />
      </div>
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-texto-3">Comentários e atribuições</p>
        <Eventos eventos={h.data!.eventos} vazio="Nenhum comentário ou atribuição." />
      </div>
    </div>
  );
}
