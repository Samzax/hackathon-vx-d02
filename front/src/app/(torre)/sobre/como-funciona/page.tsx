"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowDown } from "lucide-react";
import { Carregando, Cartao, ErroCarga, Titulo, cx } from "@/components/ui";
import { api, dados } from "@/lib/api";
import { useRadar } from "@/lib/consultas";
import { numero, usd } from "@/lib/formato";
import { useEmpresa, useTorre } from "@/lib/torre";

type Tom = "neutro" | "ia" | "pessoa" | "torre";
const TOM: Record<Tom, string> = {
  neutro: "border-borda bg-fundo-2",
  ia: "border-vence-marca/60 bg-vence-fundo",
  pessoa: "border-emdia/40 bg-emdia-fundo",
  torre: "border-marca bg-marca-suave",
};

function Caixa({ titulo, sub, tom = "neutro", forte }: { titulo: string; sub?: string; tom?: Tom; forte?: boolean }) {
  return (
    <div className={cx("rounded-lg border px-3 py-2 text-center", TOM[tom], forte && "border-2")}>
      <p className="text-sm font-semibold">{titulo}</p>
      {sub && <p className="text-xs text-texto-2">{sub}</p>}
    </div>
  );
}

function Seta({ rotulo }: { rotulo?: string }) {
  return (
    <div className="flex flex-col items-center py-1 text-texto-3" aria-hidden={!rotulo}>
      <ArrowDown className="size-4" />
      {rotulo && <span className="text-[11px]">{rotulo}</span>}
    </div>
  );
}

export default function ComoFunciona() {
  const t = useTorre();
  const empresa = useEmpresa();
  const radar = useRadar();
  const resumo = useQuery({
    queryKey: [...t.chave, "resumo"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/resumo", { params: { path: { empresa_id: empresa.id } } })),
  });
  if (resumo.isLoading || radar.isLoading) return <Carregando linhas={6} />;
  const erro = resumo.error ?? radar.error;
  if (erro) return <ErroCarga erro={erro} />;
  const r = resumo.data!;
  const f = radar.data!.funil;
  const custoRadar = radar.data!.analises.reduce((s, a) => s + a.custo_original_usd, 0);
  const extrator = radar.data!.custo_ia.find((c) => c.tarefa === "extrator");
  const filtrado = f ? ((f.atos - f.normativos) / f.atos) * 100 : null;

  return (
    <>
      <Titulo titulo="Como funciona">Dois caminhos para a mesma torre, com os números desta demo.</Titulo>
      <Cartao className="p-4 sm:p-6">
        <div className="grid gap-6 md:grid-cols-3" role="list" aria-label="Fluxo da torre">
          <div role="listitem">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-texto-3">Mudança de norma</p>
            <Caixa titulo="Diário Oficial" sub={f ? `${numero(f.atos)} atos em ${f.mes}` : undefined} />
            <Seta rotulo={f ? `${numero(f.anm)} da ANM` : undefined} />
            <Caixa titulo="Regras e busca local" sub="órgão, tipo, artigo citado · custo zero" />
            <Seta rotulo={f ? `${numero(f.normativos)} normativos` : undefined} />
            <Caixa titulo="IA barata, com cache" sub={`${usd(custoRadar)} no radar da demo`} tom="ia" />
            <Seta />
            <Caixa titulo="Conferência automática" sub="trecho, dispositivo, datas" />
            <Seta rotulo="mudança proposta" />
            <Caixa titulo="Pessoa aprova" tom="pessoa" />
          </div>
          <div role="listitem">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-texto-3">Norma inteira</p>
            <Caixa titulo="Norma" sub="ANM, NR, lei, licença" />
            <Seta />
            <Caixa titulo="Extrator + curadoria" sub={extrator ? `${extrator.n} chamadas, ${usd(extrator.usd, 3)} no total` : "IA com revisão humana"} tom="ia" />
            <Seta />
            <Caixa titulo="Cadastro versionado" sub={`${numero(r.obrigacoes)} obrigações de ${r.normas} normas`} tom="torre" />
            <Seta />
            <Caixa titulo="Torre por ativo" sub={`${r.ativos} ativos monitorados`} tom="torre" forte />
          </div>
          <div role="listitem">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-texto-3">Prova de cumprimento</p>
            <Caixa titulo="Documento da operação" sub="FIR, laudo, recibo, boletim" />
            <Seta />
            <Caixa titulo="Leitor de evidência" sub="regra primeiro; IA só se a regra não fechar" />
            <Seta />
            <Caixa titulo="Evidências" sub={`${numero(r.evidencias)} registradas`} tom="torre" />
          </div>
        </div>
      </Cartao>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Cartao className="p-4 text-sm">
          <p className="font-semibold">A IA nunca decide sozinha.</p>
          <p className="mt-1 text-texto-2">Uma conferência automática verifica se o trecho citado existe no ato e se as datas aparecem nele; uma pessoa aprova. Toda versão guarda o ato, o trecho e quem decidiu.</p>
        </Cartao>
        <Cartao className="p-4 text-sm">
          <p className="font-semibold">Regra antes de IA.</p>
          <p className="mt-1 text-texto-2">
            Órgão, tipo de ato e artigo citado resolvem {filtrado !== null ? `${numero(filtrado, 2)}%` : "quase todo"} do volume. A IA só vê o que sobra, e cada resposta fica
            em cache: a mesma pergunta nunca é paga duas vezes.
          </p>
        </Cartao>
        <Cartao className="p-4 text-sm">
          <p className="font-semibold">Traga sua chave.</p>
          <p className="mt-1 text-texto-2">Provedor e modelo são configuração (Amazon Bedrock, Anthropic e outros). A empresa pode rodar com a conta dela, e os documentos não passam pela nossa.</p>
        </Cartao>
      </div>
      <p className="mt-4 text-xs text-texto-3">
        O Diário Oficial entra pelos dados abertos da Imprensa Nacional, o canal oficial para leitura em lote.
      </p>
    </>
  );
}
