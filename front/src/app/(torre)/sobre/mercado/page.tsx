"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Carregando, Cartao, CampoEntrada, ErroCarga, Numero, Secao, Titulo } from "@/components/ui";
import { api, dados } from "@/lib/api";
import { dataBR, diasEntre, numero, reaisMilhoes } from "@/lib/formato";
import { RES_220, useTorre } from "@/lib/torre";

/** Barras horizontais de uma série só (contagem por categoria), com o valor escrito ao lado. */
function Barras({ titulo, dados: d, total }: { titulo: string; dados: Record<string, number>; total: number }) {
  const linhas = Object.entries(d).sort(([, a], [, b]) => b - a);
  const max = Math.max(1, ...linhas.map(([, v]) => v));
  return (
    <Cartao className="p-4">
      <p className="mb-3 text-sm font-semibold">{titulo}</p>
      <ul className="space-y-1.5">
        {linhas.map(([k, v]) => (
          <li key={k} className="grid grid-cols-[minmax(0,10rem)_1fr_3.5rem] items-center gap-2 text-[13px]" title={`${k}: ${v} de ${total}`}>
            <span className="truncate text-texto-2">{k}</span>
            <span className="h-2.5 rounded-r bg-fundo-3">
              <span className="block h-full rounded-r bg-marca" style={{ width: `${(v / max) * 100}%` }} />
            </span>
            <span className="num text-right font-medium">{numero(v)}</span>
          </li>
        ))}
      </ul>
    </Cartao>
  );
}

export default function Mercado() {
  const t = useTorre();
  const m = useQuery({ queryKey: ["mercado"], queryFn: () => dados(api.GET("/api/v1/mercado")), staleTime: Infinity });
  // premissas para discussão (não são dados): a pessoa ajusta
  const [preco, setPreco] = useState(1500);
  const [outros, setOutros] = useState(5);
  const [precoOutro, setPrecoOutro] = useState(150);
  const [adocao, setAdocao] = useState(10);

  if (m.isLoading) return <Carregando linhas={6} />;
  if (m.error) return <ErroCarga erro={m.error} onTentar={() => m.refetch()} />;
  const d = m.data!;
  const emergencia = Object.entries(d.pnsb_por_nivel_emergencia).filter(([k]) => k !== "Sem emergência").reduce((s, [, v]) => s + v, 0);
  const porBarragem = preco + outros * precoOutro;
  const tam = d.barragens_na_pnsb * porBarragem * 12;
  const som = (tam * adocao) / 100;
  const fora = d.barragens_mineracao - d.barragens_na_pnsb;
  const faltam = diasEntre(t.hoje, RES_220);
  const n = (e: React.ChangeEvent<HTMLInputElement>) => Math.max(0, Number(e.target.value) || 0);

  return (
    <>
      <Titulo sobre="Sobre" titulo="Mercado">Quem precisa disso, pelos dados públicos do SIGBM.</Titulo>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="mercado">
        <Numero valor={numero(d.barragens_mineracao)} rotulo="Barragens de mineração" />
        <Numero valor={numero(d.empresas)} rotulo="Empresas responsáveis" />
        <Numero valor={numero(d.barragens_na_pnsb)} rotulo="Barragens na PNSB" />
        <Numero valor={numero(d.empresas_com_barragem_na_pnsb)} rotulo="Empresas na PNSB" dica="com pelo menos uma barragem na Política Nacional" />
      </div>
      <p className="mt-2 text-xs text-texto-2">
        Fonte: {d.fonte} (exportado em {dataBR(d.exportado_em)}). Em Minas Gerais: {d.mg.barragens_na_pnsb} barragens na PNSB, de{" "}
        {d.mg.empresas_com_barragem_na_pnsb} empresas. {emergencia} barragens estão hoje em nível de alerta ou emergência.
      </p>

      <Secao titulo="Por que agora" className="mt-8">
        <ul className="list-disc space-y-1.5 pl-5 text-sm">
          <li>
            Em <strong>{dataBR(RES_220)}</strong> a Res. ANM 220/2025 substitui a Res. 95/2022: as <strong>{d.empresas_com_barragem_na_pnsb} empresas</strong> com
            barragem na PNSB terão de refazer o mapa de obrigações.{faltam > 0 ? ` Faltam ${numero(faltam)} dias.` : ""}
          </li>
          <li>A própria regra já mudou antes de valer: a Res. 245/2026 adiou parte dela para 2029. Quem acompanha norma em planilha não vê isso.</li>
          <li>A mesma mineradora responde a ANM, MTE (NR-13, NR-22) e órgão ambiental. A torre junta tudo por ativo.</li>
        </ul>
      </Secao>

      <Secao titulo="Barragens na PNSB" className="mt-8">
        <div className="grid gap-3 lg:grid-cols-2">
          <Barras titulo="Por UF" dados={d.pnsb_por_uf} total={d.barragens_na_pnsb} />
          <div className="grid gap-3">
            <Barras titulo="Nível de emergência" dados={d.pnsb_por_nivel_emergencia} total={d.barragens_na_pnsb} />
            <Barras titulo="Dano potencial associado" dados={d.pnsb_por_dano_potencial} total={d.barragens_na_pnsb} />
          </div>
        </div>
      </Secao>

      <Secao titulo="Tamanho da oportunidade (premissas ajustáveis)" className="mt-8"
        descricao="Os números de barragens e empresas são do SIGBM. Preço e adoção são premissas para discussão, não dados.">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <CampoEntrada rotulo="Preço por barragem por mês (R$)" type="number" min={0} step={250} value={preco} onChange={(e) => setPreco(n(e))} />
          <CampoEntrada rotulo="Outros ativos por barragem" type="number" min={0} value={outros} onChange={(e) => setOutros(n(e))}
            dica="vasos de pressão, licenças, unidades de mineração" />
          <CampoEntrada rotulo="Preço por outro ativo por mês (R$)" type="number" min={0} step={50} value={precoOutro} onChange={(e) => setPrecoOutro(n(e))} />
          <label className="flex flex-col gap-1">
            <span className="text-[13px] font-medium text-texto-2">Adoção entre as barragens na PNSB: {adocao}%</span>
            <input type="range" min={1} max={100} value={adocao} onChange={(e) => setAdocao(Number(e.target.value))} className="h-9 accent-[var(--marca)]" />
          </label>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Numero valor={reaisMilhoes(tam)} rotulo="Receita anual se todas as barragens da PNSB usassem" />
          <Numero valor={reaisMilhoes(som)} rotulo={`Receita anual com ${adocao}% de adoção`} />
        </div>
        <p className="mt-2 text-xs text-texto-2">
          Conta: {d.barragens_na_pnsb} barragens × (R$ {numero(preco)} + {outros} × R$ {numero(precoOutro)}) × 12 meses. Fora da conta: as {fora} barragens
          de mineração fora da PNSB e outros setores com o mesmo problema (energia, saneamento, óleo e gás).
        </p>
      </Secao>
    </>
  );
}
