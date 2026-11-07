"use client";

// A instanciação da empresa escolhida: as oito etapas, o que falta em cada uma, os dados que faltam no
// cadastro dos ativos e as unidades com os ativos de cada uma. Tudo vem da API: a tela só dá forma.
import { useQuery } from "@tanstack/react-query";
import { Factory } from "lucide-react";
import { EtapaDaInstanciacao } from "@/components/etapas";
import { Aviso, Carregando, Cartao, ErroCarga, Etiqueta, Secao, Titulo, Vazio, cx } from "@/components/ui";
import { ErroApi, api, dados, type Esquemas } from "@/lib/api";
import { dataBR, emBrasilia, plural } from "@/lib/formato";
import { useEmpresa, useTorre } from "@/lib/torre";

/** "12345678000199" -> "12.345.678/0001-99"; o que não for CNPJ de 14 dígitos volta como veio. */
function cnpjBR(cnpj: string | null): string {
  const d = (cnpj ?? "").replace(/\D/g, "");
  if (d.length !== 14) return cnpj ?? "não informado";
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

function useInstanciacao() {
  const { empresa, chave } = useTorre();
  const id = empresa?.id ?? 0;
  return useQuery({
    queryKey: [...chave, "instanciacao"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/instanciacao", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
    retry: false,
  });
}

function Resumo({ estado }: { estado: Esquemas["Estado"] }) {
  const prontas = estado.etapas.filter((e) => e.estado === "pronta").length;
  const andamento = estado.etapas.filter((e) => e.estado === "em_andamento").length;
  return (
    <>
      <Cartao className="p-4 sm:p-5" data-testid="resumo-instanciacao">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <p className="text-base font-semibold">{estado.empresa}</p>
            <p className="mt-0.5 text-[13px] text-texto-2">{estado.razao_social}</p>
            <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[13px]">
              <div className="flex gap-1.5">
                <dt className="text-texto-3">CNPJ</dt>
                <dd className="num">{cnpjBR(estado.cnpj)}</dd>
              </div>
              <div className="flex gap-1.5">
                <dt className="text-texto-3">{estado.ufs.length === 1 ? "UF" : "UFs"}</dt>
                <dd>{estado.ufs.length ? estado.ufs.join(", ") : "nenhuma informada"}</dd>
              </div>
            </dl>
          </div>

          <div className="w-full shrink-0 md:w-72">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[13px] font-medium text-texto-2">Progresso</span>
              <span className="num text-lg font-semibold">{estado.percentual}%</span>
            </div>
            <div
              role="progressbar"
              aria-label="Instanciação da empresa"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={estado.percentual}
              className="mt-1.5 h-2 overflow-hidden rounded-full bg-fundo-3"
            >
              <div
                className={cx("h-full rounded-full", estado.percentual === 100 ? "bg-emdia" : "bg-marca")}
                style={{ width: `${estado.percentual}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs text-texto-3">
              {prontas} de {estado.etapas.length} etapas prontas{andamento ? `, ${andamento} em andamento` : ""}.
            </p>
          </div>
        </div>

        <p className="mt-4 text-xs text-texto-3">
          {estado.criada_por ? `Instanciada por ${estado.criada_por}` : "Instanciação criada"} em{" "}
          {emBrasilia(estado.criada_em, false)}.
        </p>
      </Cartao>

      <div className="mt-3">
        {estado.em_operacao ? (
          <Aviso tipo="sucesso">
            Em operação desde <strong className="num">{dataBR(estado.monitorado_desde)}</strong>: a torre cobra as obrigações a partir dessa data.
          </Aviso>
        ) : (
          <Aviso tipo="atencao">
            A empresa ainda não está em operação: a torre não cobra as obrigações dela até a entrada em operação ser registrada.
          </Aviso>
        )}
      </div>
    </>
  );
}

function DadosQueFaltam() {
  const { empresa, chave } = useTorre();
  const id = empresa?.id ?? 0;
  const faltando = useQuery({
    queryKey: [...chave, "dados-faltando"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/dados-faltando", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
  const total = faltando.data?.length ?? 0;

  return (
    <Secao
      titulo={total ? `Dados que faltam (${total})` : "Dados que faltam"}
      descricao="O que as regras do catálogo pedem e ninguém informou. É lista de tarefas, não bloqueio: até o dado chegar, a obrigação fica como dado faltando, nunca presumida."
    >
      {faltando.isLoading && <Carregando linhas={3} />}
      {faltando.error && <ErroCarga erro={faltando.error} onTentar={() => faltando.refetch()} />}
      {faltando.data && total === 0 && <Aviso tipo="sucesso">Nenhum dado faltando no cadastro dos ativos.</Aviso>}
      {faltando.data && total > 0 && (
        <div className="overflow-x-auto rounded-lg border border-borda" data-testid="dados-faltando">
          <table className="w-full min-w-[680px] text-sm">
            <thead className="bg-fundo-2 text-left text-xs text-texto-2">
              <tr>
                <th className="px-3 py-2 font-medium">Ativo</th>
                <th className="px-3 py-2 font-medium">O que falta</th>
                <th className="px-3 py-2 font-medium">Obrigações que dependem</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borda">
              {faltando.data.map((d) => (
                <tr key={`${d.ativo_id}-${d.campo}`}>
                  <td className="px-3 py-2">
                    <span className="block text-xs text-texto-3">{d.ativo}</span>
                    {d.ativo_nome}
                  </td>
                  <td className="px-3 py-2">{d.pergunta}</td>
                  <td className="px-3 py-2">
                    {d.obrigacoes.length ? (
                      <ul className="flex flex-wrap gap-1">
                        {d.obrigacoes.map((o) => (
                          <li key={o}><Etiqueta tom="neutro">{o}</Etiqueta></li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-texto-3">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Secao>
  );
}

function Unidades() {
  const { empresa, chave } = useTorre();
  const id = empresa?.id ?? 0;
  const unidades = useQuery({
    queryKey: [...chave, "unidades"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/unidades", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
  const lista = unidades.data ?? [];

  return (
    <Secao
      titulo={lista.length ? `Unidades (${lista.length})` : "Unidades"}
      descricao="As operações da empresa e os ativos de cada uma."
    >
      {unidades.isLoading && <Carregando linhas={2} />}
      {unidades.error && <ErroCarga erro={unidades.error} onTentar={() => unidades.refetch()} />}
      {unidades.data && !lista.length && (
        <Vazio icone={<Factory className="size-4" />}>Nenhuma unidade cadastrada ainda.</Vazio>
      )}
      {lista.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2" data-testid="unidades">
          {lista.map((u) => (
            <li key={u.id}>
              <Cartao className="h-full p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold">{u.nome}</p>
                    <p className="text-[13px] text-texto-2">
                      {[u.municipio, u.uf].filter(Boolean).join(" · ") || "sem município e UF"}
                    </p>
                  </div>
                  <Etiqueta tom="neutro">{plural(u.ativos.length, "ativo", "ativos")}</Etiqueta>
                </div>

                {u.ativos.length ? (
                  <ul className="mt-2.5 flex flex-wrap gap-1.5">
                    {u.ativos.map((a) => <li key={a}><Etiqueta tom="marca">{a}</Etiqueta></li>)}
                  </ul>
                ) : (
                  <p className="mt-2.5 text-[13px] text-texto-2">Nenhum ativo nesta unidade.</p>
                )}

                <p className="mt-2.5 text-xs text-texto-3">
                  {u.criada_por ? `Criada por ${u.criada_por}` : "Sem registro de quem criou"} em {emBrasilia(u.criada_em, false)}.
                </p>
              </Cartao>
            </li>
          ))}
        </ul>
      )}
    </Secao>
  );
}

export default function Instanciacao() {
  const empresa = useEmpresa();
  const inst = useInstanciacao();
  const semInstanciacao = inst.error instanceof ErroApi && inst.error.status === 404;

  return (
    <>
      <Titulo sobre="Empresa" titulo="Instanciação">
        Como a empresa entrou na torre: as oito etapas, o que falta em cada uma e o que ainda depende de alguém.
      </Titulo>

      {inst.isLoading && <Carregando linhas={6} />}

      {semInstanciacao && (
        <Aviso tipo="info">
          <p className="font-semibold">A {empresa.nome} não passou pela instanciação.</p>
          <p className="mt-1">
            Ela entrou na torre por outro caminho, então não há etapas para acompanhar aqui. Esta tela vale para as
            empresas criadas pela curadoria da RegulaIA.
          </p>
        </Aviso>
      )}

      {inst.error && !semInstanciacao && <ErroCarga erro={inst.error} onTentar={() => inst.refetch()} />}

      {inst.data && (
        <>
          <Resumo estado={inst.data} />

          <Secao
            titulo="Etapas"
            descricao="Na ordem em que a empresa entra na torre; o que falta em cada uma é o próximo passo."
          >
            <ol className="space-y-2.5" data-testid="etapas">
              {inst.data.etapas.map((e, i) => (
                <EtapaDaInstanciacao key={e.etapa} etapa={e} indice={i + 1} />
              ))}
            </ol>
          </Secao>

          <DadosQueFaltam />
          <Unidades />
        </>
      )}
    </>
  );
}
