"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { FileUp, Siren } from "lucide-react";
import { useId, useState } from "react";
import { api, BASE_API, dados, enviarArquivo } from "@/lib/api";
import { useAtivos, useInvalidarTorre, type Leitura } from "@/lib/consultas";
import { dataBR, maiuscula } from "@/lib/formato";
import { useEmpresa, useTorre } from "@/lib/torre";
import { useAvisar } from "./avisos";
import { Aviso, Botao, Campo, Selecao, mensagem } from "./ui";

/** Chegou um documento da operação? PDF -> leitura (nada é gravado) -> conferência -> registro. */
export function LeitorDeDocumento() {
  const t = useTorre();
  const empresa = useEmpresa();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const ativos = useAtivos();
  const idArquivo = useId();
  const idExemplo = useId();
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [exemplo, setExemplo] = useState("");
  const [leitura, setLeitura] = useState<Leitura | null>(null);
  const exemplos = useQuery({ queryKey: ["exemplos"], queryFn: () => dados(api.GET("/api/v1/evidencias/exemplos")), staleTime: Infinity });

  const ler = useMutation({
    mutationFn: async () => {
      let doc: Blob = arquivo!;
      let nome = arquivo?.name;
      if (!arquivo) {
        const r = await fetch(`${BASE_API}/api/v1/evidencias/exemplos/${encodeURIComponent(exemplo)}`, { credentials: "include" });
        if (!r.ok) throw new Error(`não consegui abrir o exemplo ${exemplo}`);
        doc = await r.blob();
        nome = exemplo;
      }
      return enviarArquivo<Leitura>("/api/v1/evidencias/leitura", { empresa_id: empresa.id, hoje: t.hoje }, doc, nome);
    },
    onSuccess: setLeitura,
    onError: () => setLeitura(null),
  });
  const registrar = useMutation({
    mutationFn: (l: Leitura) => dados(api.POST("/api/v1/evidencias/registro", {
      body: { leitura: l.leitura, arquivo: l.arquivo, guardado_em: l.guardado_em },
    })),
    onSuccess: (_, l) => {
      const abre = l.abre.map((a) => a.codigo).join(", ");
      avisar(`Evidência registrada: ${oQue(l)}${abre ? ` · aberta em ${l.leitura.ativo}: ${abre} (24 h)` : ""}`);
      setLeitura(null);
      setArquivo(null);
      setExemplo("");
      invalidar();
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });

  const le = leitura?.leitura;
  const meus = new Set((ativos.data ?? []).map((a) => a.codigo));
  const alheio = !!le?.ativo && !!ativos.data && !meus.has(le.ativo);

  return (
    <div className="rounded-lg border border-dashed border-borda-forte bg-fundo p-4" data-testid="leitor">
      <div className="flex items-center gap-2">
        <FileUp className="size-4 text-marca" aria-hidden />
        <h2 className="text-base font-semibold">Chegou um documento da operação?</h2>
      </div>
      <p className="mt-1 text-[13px] text-texto-2">
        FIR, laudo, recibo do SIGBM ou boletim: a regra lê ativo, documento e data, e a torre dá baixa. A IA só entra se a
        regra não fechar, e o Python confere. Nada é gravado antes da sua conferência.
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Campo rotulo="Documento em PDF" htmlFor={idArquivo}>
          <input id={idArquivo} type="file" accept="application/pdf,.pdf"
            onChange={(e) => { setArquivo(e.target.files?.[0] ?? null); setLeitura(null); }}
            className="text-sm file:mr-3 file:rounded-md file:border file:border-borda-forte file:bg-fundo file:px-3 file:py-1.5 file:text-sm file:text-texto" />
        </Campo>
        <Campo rotulo="…ou um documento de exemplo" htmlFor={idExemplo}>
          <Selecao id={idExemplo} value={exemplo} disabled={!!arquivo} onChange={(e) => { setExemplo(e.target.value); setLeitura(null); }}>
            <option value="">—</option>
            {exemplos.data?.map((x) => <option key={x.nome} value={x.nome}>{x.nome}</option>)}
          </Selecao>
        </Campo>
        <Botao onClick={() => ler.mutate()} disabled={!arquivo && !exemplo} carregando={ler.isPending}>Ler documento</Botao>
      </div>
      {ler.error && <Aviso tipo="erro" className="mt-3">Não consegui ler o documento: {mensagem(ler.error)}.</Aviso>}

      {leitura && le && (
        <div className="mt-4 space-y-3" data-testid="leitura">
          <p className="text-sm">
            <strong>{leitura.arquivo}</strong>{" "}
            <span className="text-texto-2">· lido por {le.metodo === "regra" ? "regra" : "IA (conferida pelo Python)"}</span>
          </p>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 rounded-md bg-fundo-2 px-4 py-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
            {[
              ["Ativo", le.ativo], ["Documento", le.documento], ["Obrigação", le.obrigacao], ["Data de execução", dataBR(le.data)],
              ["Período comprovado", leitura.periodo_rotulo ?? le.periodo],
              ["Pontuação máxima", le.pontuacao_maxima ?? null],
            ].map(([r, v]) => (
              <div key={String(r)}>
                <dt className="text-xs text-texto-3">{r}</dt>
                <dd className="font-medium">{v ?? "—"}</dd>
              </div>
            ))}
            {!!Object.keys(le.estado_conservacao ?? {}).length && (
              <div className="col-span-full">
                <dt className="text-xs text-texto-3">Estado de conservação</dt>
                <dd className="font-medium">
                  {Object.entries(le.estado_conservacao ?? {}).sort().map(([c, v]) => `${c} ${v}`).join(" · ")}
                </dd>
              </div>
            )}
          </dl>
          {alheio && (
            <Aviso tipo="atencao">
              O documento é de {le.ativo}, que não está entre os ativos de {t.eu.visao}. Quem registra é o responsável por esse
              ativo ou a Diretoria.
            </Aviso>
          )}
          {le.gatilhos?.map((g) => (
            <Aviso key={g} tipo="erro" icone={<Siren className="size-4 text-atrasada" />}>{maiuscula(g)}</Aviso>
          ))}
          {leitura.completa && !alheio && leitura.abre.length > 0 && (
            <p className="text-[13px] text-texto-2">
              Ao registrar, a torre abre em {le.ativo}, com prazo de 24 h:{" "}
              {leitura.abre.map((a, i) => (
                <span key={a.codigo}>
                  {i > 0 && "; "}<strong className="text-texto">{a.codigo} · {a.titulo}</strong> (encerra com: {a.evidencia ?? "a evidência"})
                </span>
              ))}
              . Fica aberta até chegar esse documento.
            </p>
          )}
          {le.problemas?.map((p) => <Aviso key={p} tipo="atencao">{maiuscula(p)}</Aviso>)}
          {le.avisos?.map((a) => <Aviso key={a} tipo="info">{maiuscula(a)}</Aviso>)}
          {leitura.completa && !alheio && (t.soLeitura ? (
            <p className="text-[13px] text-texto-2" data-testid="leitura-so-leitura">
              Visão da plataforma: a leitura fica só na tela. Quem registra a evidência é a própria empresa.
            </p>
          ) : (
            <Botao variante="primario" carregando={registrar.isPending} onClick={() => registrar.mutate(leitura)}>
              Registrar evidência: {oQue(leitura)}
            </Botao>
          ))}
        </div>
      )}
    </div>
  );
}

function oQue(l: Leitura): string {
  return `${l.leitura.documento} de ${l.leitura.ativo} · ${l.periodo_rotulo ?? l.leitura.periodo}`;
}
