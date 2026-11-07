"use client";

import { useQuery } from "@tanstack/react-query";
import { FileDown, FileText } from "lucide-react";
import { useMemo, useState } from "react";
import { useAvisar } from "@/components/avisos";
import { Gantt } from "@/components/gantt";
import { Aviso, Botao, Carregando, Cartao, ErroCarga, Etiqueta, Expansivel, Numero, Secao, Titulo, Vazio, mensagem } from "@/components/ui";
import { api, baixar, dados, type Esquemas } from "@/lib/api";
import { useAtivos } from "@/lib/consultas";
import { dataBR, diasEntre, nomeDeArquivo, plural } from "@/lib/formato";
import { RES_220, useEmpresa, useTorre } from "@/lib/torre";

const HORIZONTE = "2030-03-31"; // cobre o prazo da ZAS (26/12/2029)
type Ob = Esquemas["ObrigacaoTroca"];

function Lista({ obs, soPara }: { obs: Ob[]; soPara?: boolean }) {
  if (!obs.length) return <span className="text-texto-3">—</span>;
  return (
    <ul className="space-y-1.5">
      {obs.map((o) => (
        <li key={o.codigo}>
          <p>{o.titulo}</p>
          <p className="text-xs text-texto-2">{o.dispositivo} · {soPara ? `só para ${o.aplica_se_a ?? "outros ativos"}` : o.periodicidade ?? "—"}</p>
        </li>
      ))}
    </ul>
  );
}

function Trocas() {
  const t = useTorre();
  const empresa = useEmpresa();
  const avisar = useAvisar();
  const trocas = useQuery({
    queryKey: [...t.chave, "transicao"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/transicao", { params: { path: { empresa_id: empresa.id }, query: { dia: RES_220 } } })),
  });
  const quem = t.veTudo ? "diretoria" : t.eu.area ?? t.eu.visao;
  const baixe = (formato: "pdf" | "md") =>
    baixar(`/api/v1/empresas/${empresa.id}/plano-transicao`, { formato, dia: RES_220, hoje: t.hoje }, `plano_transicao_${nomeDeArquivo(quem)}.${formato}`)
      .catch((e) => avisar(mensagem(e), "erro"));

  if (trocas.isLoading) return <Carregando linhas={4} />;
  if (trocas.error) return <ErroCarga erro={trocas.error} onTentar={() => trocas.refetch()} />;
  if (!trocas.data?.length) return <Aviso tipo="info">Nenhum dos seus ativos muda de obrigação na troca de norma.</Aviso>;
  return (
    <>
      <div className="mb-4 flex flex-wrap gap-2">
        <Botao variante="primario" tamanho="p" icone={<FileDown className="size-3.5" />} onClick={() => baixe("pdf")}>Baixar plano de transição (PDF)</Botao>
        <Botao tamanho="p" icone={<FileText className="size-3.5" />} onClick={() => baixe("md")}>Plano em texto (.md)</Botao>
      </div>
      <div className="space-y-3" data-testid="trocas">
        {trocas.data.map((tr) => (
          <Expansivel key={tr.ativo} resumo={
            <span><strong>{tr.ativo} · {tr.ativo_nome}</strong> <span className="text-texto-2">— saem {tr.saem}, entram {tr.entram}{tr.responsavel ? ` · ${tr.responsavel}` : ""}</span></span>
          }>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="text-left text-xs text-texto-2">
                  <tr>
                    <th className="w-[22%] px-2 py-2 font-medium">Tema</th>
                    <th className="px-2 py-2 font-medium">Hoje · Res. 95/2022</th>
                    <th className="px-2 py-2 font-medium">A partir de {dataBR(RES_220)} · Res. 220/2025</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borda align-top">
                  {tr.temas.map((p) => (
                    <tr key={p.tema}>
                      <td className="px-2 py-2.5"><p className="font-medium">{p.tema}</p><p className="text-xs text-texto-2">{p.situacao}</p></td>
                      <td className="px-2 py-2.5"><Lista obs={p.saem} /></td>
                      <td className="px-2 py-2.5">
                        {p.so_para_outros.length ? (
                          <><p className="mb-1 text-texto-2">Não vale para este ativo. Na Res. 220:</p><Lista obs={p.so_para_outros} soPara /></>
                        ) : <Lista obs={p.entram} />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Expansivel>
        ))}
      </div>
    </>
  );
}

function LinhaDoTempo() {
  const t = useTorre();
  const empresa = useEmpresa();
  const ativos = useAtivos();
  const [dia, setDia] = useState<string | null>(null);
  const faixas = useQuery({
    queryKey: [...t.chave, "vigencias"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/vigencias", { params: { path: { empresa_id: empresa.id } } })),
  });
  const futuras = useQuery({
    queryKey: [...t.chave, "linha-do-tempo"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/linha-do-tempo", { params: { path: { empresa_id: empresa.id }, query: { hoje: t.hoje } } })),
  });
  const porDia = useMemo(() => {
    const m = new Map<string, Map<string, { f: Esquemas["Futura"]; ativos: string[] }>>();
    for (const f of futuras.data ?? []) {
      const g = m.get(f.dia) ?? new Map();
      const k = `${f.codigo}|${f.proposta}`;
      const x = g.get(k) ?? { f, ativos: [] };
      x.ativos.push(f.ativo);
      g.set(k, x);
      m.set(f.dia, g);
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [futuras.data]);

  if (faixas.isLoading || futuras.isLoading) return <Carregando linhas={4} />;
  const erro = faixas.error ?? futuras.error;
  if (erro) return <ErroCarga erro={erro} onTentar={() => { void faixas.refetch(); void futuras.refetch(); }} />;
  return (
    <>
      <Cartao className="p-4" data-testid="gantt">
        <Gantt faixas={faixas.data ?? []} futuras={futuras.data ?? []} hoje={t.hoje} horizonte={HORIZONTE}
          marcos={[{ dia: t.hoje, rotulo: "hoje" }, ...(t.hoje < RES_220 ? [{ dia: RES_220, rotulo: "Res. 220 entra" }] : [])]}
          ordemAtivos={(ativos.data ?? []).map((a) => a.codigo)} dia={dia} onDia={setDia} />
        {!faixas.data?.length && <Vazio>Nenhuma norma vale para os seus ativos neste período.</Vazio>}
      </Cartao>
      <div className="mt-4 space-y-2">
        {porDia.map(([d, g]) => {
          const itens = [...g.values()];
          const normas = [...new Set(itens.map((x) => x.f.norma).filter(Boolean))].sort();
          return (
            <Expansivel key={`${d}-${dia === d}`} aberto={dia === d} resumo={
              <span><strong>{dataBR(d)}</strong> <span className="text-texto-2">· em {plural(diasEntre(t.hoje, d), "dia", "dias")} · {plural(itens.length, "obrigação", "obrigações")} · {normas.join(", ")}</span></span>
            }>
              <ul className="space-y-1.5 text-sm">
                {itens.map(({ f, ativos: ats }) => (
                  <li key={`${f.codigo}-${f.proposta}`}>
                    {f.proposta && <Etiqueta tom="proposta" className="mr-1.5">proposta</Etiqueta>}
                    {f.titulo} — <em className="text-texto-2">{f.dispositivo}</em> · {ats.join(", ")}
                  </li>
                ))}
              </ul>
            </Expansivel>
          );
        })}
        {!porDia.length && <Vazio>Nenhuma obrigação nova passa a valer até {dataBR(HORIZONTE)}.</Vazio>}
      </div>
    </>
  );
}

export default function Transicao() {
  const t = useTorre();
  const faltam = Math.max(0, diasEntre(t.hoje, RES_220));
  return (
    <>
      <Titulo sobre="Regulatório" titulo="Transição e linha do tempo" />
      <div className="grid gap-4 sm:grid-cols-[220px_1fr] sm:items-center">
        <Numero valor={faltam} rotulo="Dias até a Res. ANM 220/2025" />
        <p className="text-sm text-texto-2">
          Em <strong className="text-texto">{dataBR(RES_220)}</strong> a Res. ANM 95/2022 deixa de valer e a Res. ANM 220/2025 entra. Para cada
          barragem: o que sai, o que entra e o que já precisa ser preparado.
        </p>
      </div>
      <Secao titulo="O que muda em cada ativo" className="mt-8"><Trocas /></Secao>
      <Secao titulo="Linha do tempo: o que ainda vai passar a valer" className="mt-10"
        descricao="Barras: a norma que vale para cada ativo, de hoje até 2030. Losangos: dia em que obrigações passam a valer (vazado laranja = data de uma mudança ainda não aprovada). Clique num losango para ver a lista.">
        <LinhaDoTempo />
      </Secao>
    </>
  );
}
