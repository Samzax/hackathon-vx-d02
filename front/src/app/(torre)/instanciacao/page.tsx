"use client";

// A instanciação da empresa escolhida: as oito etapas, o que falta em cada uma, os dados que faltam no
// cadastro dos ativos, as unidades com os ativos de cada uma e o checklist municipal (alvarás e exigências
// do município da sede e de cada unidade) — e, para quem é da empresa, as ações: criar unidade, cadastrar
// ativo (formulário ou planilha), responder o checklist e entrar em operação. Na visão da plataforma
// tudo isso some: nos dados operacionais a Mitra só lê. Tudo vem da API: a tela só dá forma.
import { useMutation, useQuery } from "@tanstack/react-query";
import { Factory, FileDown, FileUp, Landmark, Plus, Rocket } from "lucide-react";
import Link from "next/link";
import { useId, useRef, useState } from "react";
import { useAvisar } from "@/components/avisos";
import { Dialogo } from "@/components/dialogo";
import { EtapaDaInstanciacao } from "@/components/etapas";
import {
  AreaTexto, Aviso, Botao, Campo, CampoEntrada, CampoSelecao, Carregando, Cartao, ErroCarga, Etiqueta, Secao,
  Titulo, Vazio, cx, mensagem,
} from "@/components/ui";
import { ErroApi, api, baixar, dados, enviarArquivo, type Esquemas } from "@/lib/api";
import { useCamposCadastro, useInvalidarTorre, type CampoCadastro } from "@/lib/consultas";
import { dataBR, emBrasilia, plural } from "@/lib/formato";
import {
  ROTULO_TIPO, TIPOS_ATIVO, atributosDoRascunho, cnpjBR, resumoPlanilha, type Planilha as RespostaPlanilha,
} from "@/lib/instanciacao";
import { useEmpresa, useTorre } from "@/lib/torre";

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

function useUnidades() {
  const { empresa, chave } = useTorre();
  const id = empresa?.id ?? 0;
  return useQuery({
    queryKey: [...chave, "unidades"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/unidades", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
}

/** Criar uma unidade (a própria empresa): nome, UF e município. UF nova sem conector vira lacuna
 * declarada na cobertura — e legislação municipal e alvarás entram pelo cadastro, não por fonte. */
function DialogoNovaUnidade({ onFechar }: { onFechar: () => void }) {
  const { empresa } = useTorre();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const [nome, setNome] = useState("");
  const [uf, setUf] = useState("");
  const [municipio, setMunicipio] = useState("");
  const criar = useMutation({
    mutationFn: () =>
      dados(api.POST("/api/v1/empresas/{empresa_id}/unidades", {
        params: { path: { empresa_id: empresa?.id ?? 0 } },
        body: { nome: nome.trim(), uf: uf.trim() || null, municipio: municipio.trim() || null },
      })),
    onSuccess: async (u) => {
      await invalidar();
      avisar(`Unidade criada: ${u.nome}.`);
      onFechar();
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  return (
    <Dialogo aberto onFechar={onFechar} titulo="Nova unidade"
      rodape={<>
        <Botao onClick={onFechar}>Cancelar</Botao>
        <Botao variante="primario" disabled={nome.trim().length < 2} carregando={criar.isPending}
          onClick={() => criar.mutate()}>Criar a unidade</Botao>
      </>}>
      <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); if (nome.trim().length >= 2) criar.mutate(); }}>
        <CampoEntrada rotulo="Nome" value={nome} onChange={(e) => setNome(e.target.value)}
          placeholder="Mina Serra Azul" required minLength={2} />
        <div className="grid grid-cols-2 gap-3">
          <CampoEntrada rotulo="UF" value={uf} onChange={(e) => setUf(e.target.value)} placeholder="MG" maxLength={2} />
          <CampoEntrada rotulo="Município" value={municipio} onChange={(e) => setMunicipio(e.target.value)}
            placeholder="Itabirito" />
        </div>
      </form>
    </Dialogo>
  );
}

function Unidades() {
  const { soLeitura } = useTorre();
  const unidades = useUnidades();
  const [criando, setCriando] = useState(false);
  const lista = unidades.data ?? [];

  return (
    <Secao
      titulo={lista.length ? `Unidades (${lista.length})` : "Unidades"}
      descricao="As operações da empresa e os ativos de cada uma."
      acoes={!soLeitura && (
        <Botao tamanho="p" icone={<Plus className="size-3.5" />} onClick={() => setCriando(true)}>
          Nova unidade
        </Botao>
      )}
    >
      {criando && <DialogoNovaUnidade onFechar={() => setCriando(false)} />}
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

// ------------------------------------------------------------------ etapa 5: o checklist municipal

type ItemMunicipal = Esquemas["ItemMunicipal"];
type Resposta = "confirmado" | "nao_se_aplica";

type Situacao = "pendente" | Resposta;
const SITUACAO_MUNICIPAL: Record<Situacao, { rotulo: string; tom: "neutro" | "ok" | "atencao" }> = {
  pendente: { rotulo: "Pendente", tom: "atencao" },
  confirmado: { rotulo: "Confirmado", tom: "ok" },
  nao_se_aplica: { rotulo: "Não se aplica", tom: "neutro" },
};

/** Confirmar ou dizer que não se aplica. A nota é obrigatória em "não se aplica" e ao confirmar um local
 * sem alvará enviado — a API confere e devolve o erro; aqui só se evita mandar o que ela vai recusar. */
function DialogoMunicipal({ item, resposta, onFechar }:
  { item: ItemMunicipal; resposta: Resposta; onFechar: () => void }) {
  const { empresa } = useTorre();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const id = useId();
  const [nota, setNota] = useState("");
  const exigeNota = resposta === "nao_se_aplica" || item.alvaras.length === 0;
  const responder = useMutation({
    mutationFn: () =>
      dados(api.PUT("/api/v1/empresas/{empresa_id}/instanciacao/municipal", {
        params: { path: { empresa_id: empresa?.id ?? 0 } },
        body: { local: item.local, situacao: resposta, nota: nota.trim() || null },
      })),
    onSuccess: async () => {
      await invalidar();
      avisar(`${item.titulo}: ${SITUACAO_MUNICIPAL[resposta].rotulo.toLowerCase()}.`);
      onFechar();
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  const pronto = !exigeNota || nota.trim().length > 0;
  return (
    <Dialogo aberto onFechar={onFechar}
      titulo={resposta === "confirmado" ? `Confirmar: ${item.titulo}` : `Não se aplica: ${item.titulo}`}
      rodape={<>
        <Botao onClick={onFechar}>Cancelar</Botao>
        <Botao variante="primario" disabled={!pronto} carregando={responder.isPending}
          onClick={() => responder.mutate()}>
          {resposta === "confirmado" ? "Confirmar" : "Registrar"}
        </Botao>
      </>}>
      <div className="grid gap-3 text-sm">
        {resposta === "confirmado" && item.alvaras.length > 0 && (
          <p>
            {item.alvaras.length === 1 ? "Alvará enviado" : "Alvarás enviados"}: <strong>{item.alvaras.join(", ")}</strong>.
            Confirme que as demais exigências do município também foram entregues.
          </p>
        )}
        {resposta === "confirmado" && item.alvaras.length === 0 && (
          <Aviso tipo="atencao">
            Nenhum alvará deste local foi enviado em Licenças. Para confirmar mesmo assim, diga o que foi entregue
            (ex.: protocolo da renovação na prefeitura).
          </Aviso>
        )}
        <Campo htmlFor={id} rotulo={exigeNota ? "Nota (obrigatória)" : "Nota (opcional)"}
          dica={resposta === "nao_se_aplica"
            ? "Por que não se aplica: ex.: o município dispensa alvará para esta atividade." : undefined}>
          <AreaTexto id={id} value={nota} onChange={(e) => setNota(e.target.value)} maxLength={1000} />
        </Campo>
      </div>
    </Dialogo>
  );
}

function ChecklistMunicipal() {
  const t = useTorre();
  const id = t.empresa?.id ?? 0;
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const [aberto, setAberto] = useState<{ item: ItemMunicipal; resposta: Resposta } | null>(null);
  const checklist = useQuery({
    queryKey: [...t.chave, "municipal"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/instanciacao/municipal",
      { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
  const reabrir = useMutation({
    mutationFn: (item: ItemMunicipal) =>
      dados(api.PUT("/api/v1/empresas/{empresa_id}/instanciacao/municipal", {
        params: { path: { empresa_id: id } }, body: { local: item.local, situacao: "pendente", nota: null },
      })),
    onSuccess: async (_, item) => {
      await invalidar();
      avisar(`${item.titulo} voltou a pendente.`);
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  const responde = !t.soLeitura && t.veTudo;
  const pendentes = checklist.data?.pendentes ?? 0;

  return (
    <Secao
      titulo={pendentes
        ? `Alvarás e exigências municipais (${plural(pendentes, "pendente", "pendentes")})`
        : "Alvarás e exigências municipais"}
      descricao="Etapa 5. Legislação municipal e alvarás não têm fonte automática: entram pelo cadastro, na implantação. A sede e cada unidade respondem; o alvará enviado em Licenças aparece como prova do local."
    >
      {aberto && <DialogoMunicipal item={aberto.item} resposta={aberto.resposta} onFechar={() => setAberto(null)} />}
      {checklist.isLoading && <Carregando linhas={2} />}
      {checklist.error && <ErroCarga erro={checklist.error} onTentar={() => checklist.refetch()} />}
      {checklist.data && (
        <>
          <p className="mb-3 text-[13px] text-texto-2">{checklist.data.pergunta}</p>
          <ul className="grid gap-3 md:grid-cols-2" data-testid="checklist-municipal">
            {checklist.data.itens.map((i) => {
              const s = SITUACAO_MUNICIPAL[i.situacao as Situacao] ?? SITUACAO_MUNICIPAL.pendente;
              return (
                <li key={i.local || "sede"}>
                  <Cartao className="flex h-full flex-col p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold">{i.titulo}</p>
                        <p className="text-[13px] text-texto-2">
                          {[i.municipio, i.uf].filter(Boolean).join(" · ") || (i.local ? "sem município e UF" : "a empresa")}
                        </p>
                      </div>
                      <Etiqueta tom={s.tom}>{s.rotulo}</Etiqueta>
                    </div>
                    <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[13px]">
                      {i.alvaras.length ? (
                        i.alvaras.map((a) => <Etiqueta key={a} tom="marca">Alvará {a}</Etiqueta>)
                      ) : (
                        <span className="text-texto-3">Nenhum alvará enviado.</span>
                      )}
                    </div>
                    {i.nota && <p className="mt-2 text-[13px]">“{i.nota}”</p>}
                    {i.por && i.em && (
                      <p className="mt-2 text-xs text-texto-3">{s.rotulo} por {i.por} em {emBrasilia(i.em, false)}.</p>
                    )}
                    {responde && (
                      <div className="mt-auto flex flex-wrap gap-2 pt-3">
                        {i.situacao === "pendente" ? (
                          <>
                            <Botao tamanho="p" variante="primario"
                              onClick={() => setAberto({ item: i, resposta: "confirmado" })}>
                              Confirmar
                            </Botao>
                            <Botao tamanho="p" onClick={() => setAberto({ item: i, resposta: "nao_se_aplica" })}>
                              Não se aplica
                            </Botao>
                          </>
                        ) : (
                          <Botao tamanho="p" carregando={reabrir.isPending && reabrir.variables?.local === i.local}
                            onClick={() => reabrir.mutate(i)}>
                            Reabrir
                          </Botao>
                        )}
                      </div>
                    )}
                  </Cartao>
                </li>
              );
            })}
          </ul>
          {responde && (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-texto-3">
              <Landmark className="size-3.5" aria-hidden />
              O PDF do alvará entra em <Link href="/licencas" className="underline">Licenças</Link>, com o tipo alvará e a unidade.
            </p>
          )}
        </>
      )}
    </Secao>
  );
}

// ------------------------------------------------------------------ cadastrar ativos (a empresa)

/** O campo do cadastro no tipo certo: sim/não, opções pelo rótulo, data, número ou texto. O valor
 * segue como texto e quem converte e confere é a API — valor que não serve volta com o erro. */
function EntradaDoCampo({ campo, valor, onChange }:
  { campo: CampoCadastro; valor: string; onChange: (v: string) => void }) {
  if (campo.tipo === "booleano") {
    return (
      <CampoSelecao rotulo={campo.rotulo} value={valor} onChange={(e) => onChange(e.target.value)} dica={campo.pergunta}>
        <option value="">não informado</option>
        <option value="sim">sim</option>
        <option value="não">não</option>
      </CampoSelecao>
    );
  }
  if (campo.tipo === "opcoes") {
    return (
      <CampoSelecao rotulo={campo.rotulo} value={valor} onChange={(e) => onChange(e.target.value)} dica={campo.pergunta}>
        <option value="">não informado</option>
        {campo.opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
      </CampoSelecao>
    );
  }
  return (
    <CampoEntrada rotulo={campo.rotulo} value={valor} onChange={(e) => onChange(e.target.value)}
      dica={campo.pergunta} type={campo.tipo === "data" ? "date" : "text"}
      inputMode={campo.tipo === "numero" ? "decimal" : undefined} />
  );
}

function FormularioAtivo() {
  const { empresa } = useTorre();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const campos = useCamposCadastro();
  const unidades = useUnidades();
  const [tipo, setTipo] = useState<(typeof TIPOS_ATIVO)[number]>("barragem");
  const [codigo, setCodigo] = useState("");
  const [nome, setNome] = useState("");
  const [unidade, setUnidade] = useState("");
  const [responsavel, setResponsavel] = useState("");
  const [rascunho, setRascunho] = useState<Record<string, string>>({});

  const doTipo = (campos.data ?? []).filter((c) => c.tipos_ativo.includes(tipo) && c.campo !== "alertas_sigbm");
  const criar = useMutation({
    mutationFn: () =>
      dados(api.POST("/api/v1/empresas/{empresa_id}/instanciacao/ativos", {
        params: { path: { empresa_id: empresa?.id ?? 0 } },
        body: {
          tipo, codigo: codigo.trim(), nome: nome.trim(), unidade: unidade || null,
          responsavel: responsavel.trim() || null, atributos: atributosDoRascunho(rascunho),
        },
      })),
    onSuccess: async (r) => {
      await invalidar();
      avisar(`Ativo cadastrado: ${r.codigo}. O que ficou sem valor aparece em dados que faltam.`);
      setCodigo(""); setNome(""); setRascunho({});
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  const pronto = codigo.trim().length >= 1 && nome.trim().length >= 1;

  return (
    <Cartao className="p-4 sm:p-5">
      <form className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="novo-ativo"
        onSubmit={(e) => { e.preventDefault(); if (pronto) criar.mutate(); }}>
        <CampoSelecao rotulo="Tipo" value={tipo}
          onChange={(e) => { setTipo(e.target.value as (typeof TIPOS_ATIVO)[number]); setRascunho({}); }}>
          {TIPOS_ATIVO.map((t) => <option key={t} value={t}>{ROTULO_TIPO[t]}</option>)}
        </CampoSelecao>
        <CampoEntrada rotulo="Código" value={codigo} onChange={(e) => setCodigo(e.target.value)}
          placeholder="B1" required dica="Único na empresa; é como a torre chama o ativo." />
        <CampoEntrada rotulo="Nome" value={nome} onChange={(e) => setNome(e.target.value)}
          placeholder="Barragem Nova" required />
        <CampoSelecao rotulo="Unidade" value={unidade} onChange={(e) => setUnidade(e.target.value)}
          dica="A operação a que o ativo pertence (crie a unidade antes).">
          <option value="">sem unidade</option>
          {(unidades.data ?? []).map((u) => <option key={u.id} value={u.nome}>{u.nome}</option>)}
        </CampoSelecao>
        <CampoEntrada rotulo="Área responsável" value={responsavel} onChange={(e) => setResponsavel(e.target.value)}
          placeholder="Gerência de Geotecnia" />
        {doTipo.map((c) => (
          <EntradaDoCampo key={c.campo} campo={c} valor={rascunho[c.campo] ?? ""}
            onChange={(v) => setRascunho((r) => ({ ...r, [c.campo]: v }))} />
        ))}
        <div className="sm:col-span-2 lg:col-span-3">
          <Botao type="submit" variante="primario" icone={<Plus className="size-4" />} disabled={!pronto}
            carregando={criar.isPending}>
            Cadastrar o ativo
          </Botao>
        </div>
      </form>
    </Cartao>
  );
}

function PlanilhaDeAtivos() {
  const { empresa } = useTorre();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const [tipoModelo, setTipoModelo] = useState<(typeof TIPOS_ATIVO)[number]>("barragem");
  const [resultado, setResultado] = useState<RespostaPlanilha | null>(null);
  const [soConferiu, setSoConferiu] = useState(true);
  const arquivoRef = useRef<HTMLInputElement>(null);

  const enviar = useMutation({
    mutationFn: async ({ conferir }: { conferir: boolean }) => {
      const arquivo = arquivoRef.current?.files?.[0];
      if (!arquivo) throw new Error("escolha a planilha CSV primeiro");
      const r = await enviarArquivo<RespostaPlanilha>(
        `/api/v1/empresas/${empresa?.id ?? 0}/instanciacao/planilha`, { conferir }, arquivo);
      return { r, conferir };
    },
    onSuccess: async ({ r, conferir }) => {
      setResultado(r);
      setSoConferiu(conferir);
      if (!conferir && r.importados) await invalidar();
      avisar(resumoPlanilha(r, conferir), r.erros ? "erro" : "ok");
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });

  const comErro = resultado?.linhas.filter((l) => l.erro) ?? [];

  return (
    <Cartao className="p-4 sm:p-5">
      <div className="flex flex-wrap items-end gap-3">
        <CampoSelecao rotulo="Modelo por tipo" className="w-56" value={tipoModelo}
          onChange={(e) => setTipoModelo(e.target.value as (typeof TIPOS_ATIVO)[number])}>
          {TIPOS_ATIVO.map((t) => <option key={t} value={t}>{ROTULO_TIPO[t]}</option>)}
        </CampoSelecao>
        <Botao icone={<FileDown className="size-4" />}
          onClick={() => baixar("/api/v1/instanciacoes/modelo.csv", { tipo: tipoModelo }, `modelo_${tipoModelo}.csv`)
            .catch((e) => avisar(mensagem(e), "erro"))}>
          Baixar o modelo
        </Botao>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-borda pt-4">
        <input ref={arquivoRef} type="file" accept=".csv,text/csv" aria-label="Planilha CSV de ativos"
          className="text-sm file:mr-3 file:rounded-md file:border file:border-borda-forte file:bg-fundo file:px-3 file:py-1.5 file:text-sm file:text-texto" />
        <Botao carregando={enviar.isPending} onClick={() => enviar.mutate({ conferir: true })}>
          Só conferir
        </Botao>
        <Botao variante="primario" icone={<FileUp className="size-4" />} carregando={enviar.isPending}
          onClick={() => enviar.mutate({ conferir: false })}>
          Importar (tudo ou nada)
        </Botao>
      </div>
      <p className="mt-2 text-xs text-texto-3">
        A planilha é validada linha a linha, com o erro na linha, como a pessoa vê no arquivo. Com qualquer
        erro, nada é gravado.
      </p>
      {resultado && (
        <div className="mt-3">
          <Aviso tipo={resultado.erros ? "erro" : "sucesso"}>{resumoPlanilha(resultado, soConferiu)}</Aviso>
          {comErro.length > 0 && (
            <div className="mt-2 overflow-x-auto rounded-lg border border-borda" data-testid="erros-planilha">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="bg-fundo-2 text-left text-xs text-texto-2">
                  <tr>
                    <th className="px-3 py-2 font-medium">Linha</th>
                    <th className="px-3 py-2 font-medium">Código</th>
                    <th className="px-3 py-2 font-medium">O que está errado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borda">
                  {comErro.map((l) => (
                    <tr key={l.linha}>
                      <td className="num px-3 py-2">{l.linha}</td>
                      <td className="px-3 py-2">{l.codigo || "—"}</td>
                      <td className="px-3 py-2 text-atrasada">{l.erro}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Cartao>
  );
}

// ------------------------------------------------------------------ entrar em operação

function EntrarEmOperacao() {
  const t = useTorre();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const [desde, setDesde] = useState(t.hoje);
  const [pendencias, setPendencias] = useState<string[] | null>(null);
  const entrar = useMutation({
    mutationFn: () =>
      dados(api.POST("/api/v1/empresas/{empresa_id}/instanciacao/operacao", {
        params: { path: { empresa_id: t.empresa?.id ?? 0 } },
        body: { desde: desde || null },
      })),
    onSuccess: async (r) => {
      await invalidar();
      setPendencias(r.pendencias);
      avisar(`Em operação desde ${dataBR(r.monitorado_desde)}: a torre passou a cobrar.`);
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  return (
    <Secao
      titulo="Entrar em operação"
      descricao="Etapa 8: a torre passa a cobrar as obrigações a partir da data. Dá para entrar com pendências — elas continuam visíveis."
    >
      <Cartao className="flex flex-wrap items-end gap-3 p-4 sm:p-5" data-testid="entrar-operacao">
        <CampoEntrada rotulo="A torre cobra a partir de" type="date" className="w-52" value={desde}
          onChange={(e) => setDesde(e.target.value)} />
        <Botao variante="primario" icone={<Rocket className="size-4" />} carregando={entrar.isPending}
          onClick={() => entrar.mutate()}>
          Entrar em operação
        </Botao>
        {pendencias && pendencias.length > 0 && (
          <p className="w-full text-[13px] text-texto-2">
            Etapas que seguem pendentes: {pendencias.join(", ")}.
          </p>
        )}
      </Cartao>
    </Secao>
  );
}

export default function Instanciacao() {
  const t = useTorre();
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
            empresas criadas pela curadoria da Mitra.
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

          <Unidades />

          <ChecklistMunicipal />

          {!t.soLeitura && (
            <>
              <Secao
                titulo="Cadastrar ativos"
                descricao="Etapa 2, da própria empresa: barragens, minas, usinas, equipamentos, licenças e obras, um a um. O que ficar sem valor vira dado faltando, nunca é presumido."
              >
                <FormularioAtivo />
              </Secao>
              <Secao
                titulo="Planilha de ativos"
                descricao="O mesmo cadastro em lote: baixe o modelo do tipo, preencha e importe."
              >
                <PlanilhaDeAtivos />
              </Secao>
            </>
          )}

          <DadosQueFaltam />

          {!t.soLeitura && t.veTudo && !inst.data.em_operacao && <EntrarEmOperacao />}
          {t.soLeitura && (
            <Aviso tipo="info" className="mt-8">
              Visão da plataforma: aqui só se lê. Quem cadastra unidade e ativo, preenche o que falta e entra em
              operação é a própria empresa.
            </Aviso>
          )}
        </>
      )}
    </>
  );
}
