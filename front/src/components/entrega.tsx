"use client";

import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useId, useState } from "react";
import { api, dados } from "@/lib/api";
import { type Linha, useEntregar } from "@/lib/consultas";
import { GATILHO } from "@/lib/status";
import { useTorre } from "@/lib/torre";
import { useAvisar } from "./avisos";
import { Dialogo } from "./dialogo";
import { AreaTexto, Aviso, Botao, Campo, CampoEntrada, Selo, mensagem } from "./ui";

export type AlvoEntrega = Pick<Linha, "ativo_id" | "ativo" | "codigo" | "titulo" | "status"> &
  Partial<Pick<Linha, "dispositivo" | "evidencia" | "pendente" | "agenda">>;

/** Registrar a entrega: dia, o período que ela comprova (a API diz qual), comprovante opcional e observação. */
export function FormEntrega({ alvo, onFeito, idForm }: { alvo: AlvoEntrega; onFeito?: () => void; idForm?: string }) {
  const t = useTorre();
  const avisar = useAvisar();
  const [dia, setDia] = useState(t.hoje);
  const [obs, setObs] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const idArquivo = useId();
  const idObs = useId();
  const entregar = useEntregar();
  const periodo = useQuery({
    queryKey: [...t.chave, "periodo", alvo.ativo_id, alvo.codigo, dia],
    queryFn: () => dados(api.GET("/api/v1/entregas/periodo", { params: { query: { ativo_id: alvo.ativo_id!, codigo: alvo.codigo, dia } } })),
    enabled: !!alvo.ativo_id && !!dia,
  });

  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    entregar.mutate({ ativo_id: alvo.ativo_id!, codigo: alvo.codigo, dia, obs, arquivo }, {
      onSuccess: (r) => {
        avisar(`Entrega registrada: ${alvo.ativo} · ${alvo.codigo} · ${r.periodo_rotulo}`);
        setObs("");
        setArquivo(null);
        onFeito?.();
      },
    });
  };

  return (
    <form id={idForm} onSubmit={enviar} className="space-y-3">
      {alvo.agenda === "evento" && alvo.status === GATILHO && (
        <p className="text-[13px] text-texto-2">Obrigação por gatilho: registre quando o evento acontecer.</p>
      )}
      <CampoEntrada rotulo="Feita em" type="date" value={dia} max={t.hoje} required onChange={(e) => setDia(e.target.value)} />
      <p className="text-[13px] text-texto-2" aria-live="polite">
        Comprova:{" "}
        <strong className="text-texto" data-testid="periodo-comprovado">
          {periodo.data?.rotulo ?? (periodo.isFetching ? "…" : "—")}
        </strong>
      </p>
      {periodo.error && <Aviso tipo="atencao">{mensagem(periodo.error)}.</Aviso>}
      <Campo rotulo="Comprovante (opcional)" htmlFor={idArquivo} dica="Fica guardado com o registro (pasta da torre ou S3). Até 20 MB.">
        <input id={idArquivo} type="file" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
          className="text-sm file:mr-3 file:rounded-md file:border file:border-borda-forte file:bg-fundo file:px-3 file:py-1.5 file:text-sm file:text-texto" />
      </Campo>
      <Campo rotulo="Observação" htmlFor={idObs}>
        <AreaTexto id={idObs} value={obs} onChange={(e) => setObs(e.target.value)} rows={2} placeholder="ex.: laudo entregue pela consultoria" />
      </Campo>
      {entregar.error && <Aviso tipo="erro">{mensagem(entregar.error)}.</Aviso>}
      {!idForm && (
        <Botao type="submit" variante="primario" icone={<Check className="size-4" />} carregando={entregar.isPending}>
          Registrar entrega
        </Botao>
      )}
    </form>
  );
}

export function DialogoEntrega({ alvo, onFechar }: { alvo: AlvoEntrega | null; onFechar: () => void }) {
  const idForm = useId();
  return (
    <Dialogo
      aberto={!!alvo}
      onFechar={onFechar}
      titulo="Registrar entrega"
      rodape={alvo && <>
        <Botao onClick={onFechar}>Cancelar</Botao>
        <Botao type="submit" form={idForm} variante="primario" icone={<Check className="size-4" />}>Registrar entrega</Botao>
      </>}
    >
      {alvo && (
        <>
          <div className="mb-4">
            <div className="flex flex-wrap items-center gap-2">
              <Selo status={alvo.status} />
              <span className="font-semibold">{alvo.ativo} · {alvo.titulo}</span>
            </div>
            <p className="mt-1 text-[13px] text-texto-2">
              {alvo.dispositivo}
              {alvo.evidencia ? ` · evidência: ${alvo.evidencia}` : ""}
              {alvo.pendente ? ` · pendente: ${alvo.pendente}` : ""}
            </p>
          </div>
          <FormEntrega key={`${alvo.ativo_id}-${alvo.codigo}`} alvo={alvo} idForm={idForm} onFeito={onFechar} />
        </>
      )}
    </Dialogo>
  );
}
