"use client";

// Pessoas e unidades da empresa: os responsáveis técnicos — CPF sempre mascarado, com o "Ver CPF"
// auditado — e as unidades com os ativos de cada uma. Quem escreve é a própria empresa; a plataforma
// (useTorre().soLeitura) só lê, e a TI não vê dado regulatório.
import { useMutation, useQuery } from "@tanstack/react-query";
import { Eye, EyeOff, Factory, Trash2, UserPlus } from "lucide-react";
import { useState } from "react";
import { useAvisar } from "@/components/avisos";
import { Dialogo } from "@/components/dialogo";
import {
  Aviso, Botao, Carregando, Cartao, CampoEntrada, CampoSelecao, ErroCarga, Etiqueta, Secao, Vazio, mensagem,
} from "@/components/ui";
import { api, dados, type Esquemas } from "@/lib/api";
import { useInvalidarTorre } from "@/lib/consultas";
import { dataBR, emBrasilia, plural } from "@/lib/formato";
import { useTorre } from "@/lib/torre";

export type Responsavel = Esquemas["Responsavel-Output"];
export type Unidade = Esquemas["Unidade"];

// ------------------------------------------------------------------ consultas

export function useResponsaveis() {
  const { empresa, chave } = useTorre();
  const id = empresa?.id ?? 0;
  return useQuery({
    queryKey: [...chave, "responsaveis"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/responsaveis", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
}

/** Os papéis são fixos: não dependem da empresa nem do dia. */
export function usePapeis() {
  return useQuery({
    queryKey: ["responsaveis-papeis"],
    queryFn: () => dados(api.GET("/api/v1/responsaveis/papeis")),
    staleTime: Infinity,
  });
}

export function useUnidades() {
  const { empresa, chave, ti } = useTorre();
  const id = empresa?.id ?? 0;
  return useQuery({
    queryKey: [...chave, "unidades"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/unidades", { params: { path: { empresa_id: id } } })),
    enabled: !!id && !ti, // a TI administra contas e não vê dado regulatório
    retry: false,
  });
}

// ------------------------------------------------------------------ CPF (ver é auditado)

function CpfDoResponsavel({ r }: { r: Responsavel }) {
  const t = useTorre();
  const id = t.empresa?.id ?? 0;
  const [cpf, setCpf] = useState<string | null>(null);
  const ver = useMutation({
    mutationFn: () => dados(api.GET("/api/v1/responsaveis/{responsavel_id}/cpf", {
      params: { path: { responsavel_id: r.id }, query: { empresa_id: id } },
    })),
    onSuccess: (d) => setCpf(d.cpf),
  });

  return (
    <div className="sm:col-span-2">
      <dt className="text-texto-3">CPF</dt>
      <dd className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="num">{cpf ?? r.cpf_mascarado}</span>
          {!t.soLeitura && (
            <Botao tamanho="p" variante="fantasma" carregando={ver.isPending}
              icone={cpf ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
              onClick={() => {
                if (cpf) return setCpf(null);
                ver.reset();
                ver.mutate();
              }}
              aria-label={`${cpf ? "Ocultar" : "Ver"} o CPF de ${r.nome}`}>
              {cpf ? "Ocultar" : "Ver CPF"}
            </Botao>
          )}
        </div>
        {ver.error && <Aviso tipo="erro">{mensagem(ver.error)}.</Aviso>}
        {cpf && <Aviso tipo="info">A visualização do CPF ficou registrada na auditoria.</Aviso>}
      </dd>
    </div>
  );
}

// ------------------------------------------------------------------ um responsável

function CartaoResponsavel({ r }: { r: Responsavel }) {
  const t = useTorre();
  const id = t.empresa?.id ?? 0;
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const [confirmar, setConfirmar] = useState(false);
  const remover = useMutation({
    mutationFn: () => dados(api.DELETE("/api/v1/responsaveis/{responsavel_id}", {
      params: { path: { responsavel_id: r.id }, query: { empresa_id: id } },
    })),
    onSuccess: () => {
      setConfirmar(false);
      avisar(`${r.nome} saiu dos responsáveis técnicos da empresa`);
      invalidar();
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  const responde = [r.unidade, r.ativo_codigo ? `ativo ${r.ativo_codigo}` : null].filter(Boolean).join(" · ");

  return (
    <li>
      <Cartao className="h-full p-4" data-testid="responsavel">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-1.5 text-sm font-semibold">
              {r.nome}
              {r.ficticio && <Etiqueta tom="neutro">fictício</Etiqueta>}
            </p>
            <p className="text-[13px] text-texto-2">{r.papel_rotulo}</p>
          </div>
          {!t.soLeitura && !t.ti && (
            <Botao tamanho="p" variante="fantasma" icone={<Trash2 className="size-3.5" />}
              onClick={() => setConfirmar(true)} aria-label={`Remover ${r.nome}`}>
              Remover
            </Botao>
          )}
        </div>

        <dl className="mt-3 grid gap-x-4 gap-y-2 text-[13px] sm:grid-cols-2">
          <CpfDoResponsavel r={r} />
          {r.registro && (
            <div>
              <dt className="text-texto-3">Registro no conselho</dt>
              <dd>{r.registro}</dd>
            </div>
          )}
          {r.art_numero && (
            <div>
              <dt className="text-texto-3">ART</dt>
              <dd>
                {r.art_numero}
                {r.art_vigencia_ate && <span className="text-texto-2"> · vence {dataBR(r.art_vigencia_ate)}</span>}
              </dd>
            </div>
          )}
          <div className="sm:col-span-2">
            <dt className="text-texto-3">Responde por</dt>
            <dd>{responde || "—"}</dd>
          </div>
        </dl>

        <p className="mt-2.5 text-xs text-texto-3">
          {r.criado_por ? `Cadastrado por ${r.criado_por}` : "Sem registro de quem cadastrou"} em {emBrasilia(r.criado_em, false)}.
        </p>
      </Cartao>

      <Dialogo aberto={confirmar} onFechar={() => setConfirmar(false)} titulo={`Remover ${r.nome}?`}
        rodape={
          <>
            <Botao variante="fantasma" onClick={() => setConfirmar(false)}>Cancelar</Botao>
            <Botao variante="perigo" icone={<Trash2 className="size-4" />} carregando={remover.isPending}
              onClick={() => remover.mutate()}>Remover</Botao>
          </>
        }>
        <p className="text-sm">O cadastro sai da lista de responsáveis técnicos da empresa. A remoção fica registrada na auditoria.</p>
        {remover.error && <Aviso tipo="erro" className="mt-3">{mensagem(remover.error)}.</Aviso>}
      </Dialogo>
    </li>
  );
}

// ------------------------------------------------------------------ cadastro de um responsável

function FormResponsavel() {
  const t = useTorre();
  const id = t.empresa?.id ?? 0;
  const papeis = usePapeis();
  const unidades = useUnidades();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const vazio = {
    nome: "", cpf: "", registro: "", art_numero: "", art_vigencia_ate: "", unidade: "", ativo_codigo: "", consentimento: "",
  };
  const [f, setF] = useState(vazio);
  const [papel, setPapel] = useState("");
  const mapa = papeis.data?.papeis ?? {};
  const escolhido = papel || Object.keys(mapa)[0] || "";
  const listaUnidades = unidades.data ?? [];
  const codigos = listaUnidades.flatMap((u) => u.ativos);

  const criar = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/empresas/{empresa_id}/responsaveis", {
      params: { path: { empresa_id: id } },
      body: {
        papel: escolhido,
        nome: f.nome.trim(),
        cpf: f.cpf.trim() || null,
        registro: f.registro.trim() || null,
        art_numero: f.art_numero.trim() || null,
        art_vigencia_ate: f.art_vigencia_ate || null,
        unidade: f.unidade || null,
        ativo_codigo: f.ativo_codigo.trim() || null,
        ficticio: false,
        consentimento_para: f.consentimento.trim() || null,
      },
    })),
    onSuccess: (d) => {
      const nome = f.nome.trim();
      avisar(d.obrigacao_art
        ? `${nome} cadastrado; a renovação da ART entrou na torre como ${d.obrigacao_art}.`
        : `${nome} cadastrado como ${mapa[escolhido]?.toLowerCase() ?? "responsável"}.`);
      setF(vazio);
      setPapel("");
      invalidar();
    },
  });

  if (papeis.isLoading) return <Carregando linhas={2} />;
  if (papeis.error) return <ErroCarga erro={papeis.error} onTentar={() => papeis.refetch()} />;

  return (
    <form className="grid gap-3 sm:grid-cols-2" data-testid="form-responsavel" onSubmit={(e) => { e.preventDefault(); criar.mutate(); }}>
      <CampoSelecao rotulo="Papel" value={escolhido} onChange={(e) => setPapel(e.target.value)}>
        {Object.entries(mapa).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </CampoSelecao>
      <CampoEntrada rotulo="Nome" required value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />
      <CampoEntrada rotulo="CPF" value={f.cpf} inputMode="numeric" autoComplete="off" placeholder="somente dígitos"
        onChange={(e) => setF({ ...f, cpf: e.target.value })}
        dica="Guardado cifrado. A lista mostra sempre mascarado; ver o número inteiro fica na auditoria." />
      <CampoEntrada rotulo="Registro no conselho" value={f.registro} placeholder="ex.: CREA MG-123456"
        onChange={(e) => setF({ ...f, registro: e.target.value })} />
      <CampoEntrada rotulo="ART" value={f.art_numero} placeholder="número da ART"
        onChange={(e) => setF({ ...f, art_numero: e.target.value })} />
      <CampoEntrada rotulo="ART vale até" type="date" value={f.art_vigencia_ate}
        onChange={(e) => setF({ ...f, art_vigencia_ate: e.target.value })}
        dica="Com data de validade, a renovação entra na torre como obrigação." />
      <CampoSelecao rotulo="Unidade" value={f.unidade}
        onChange={(e) => setF({ ...f, unidade: e.target.value })}>
        <option value="">—</option>
        {listaUnidades.map((u) => <option key={u.id} value={u.nome}>{u.nome}</option>)}
      </CampoSelecao>
      <CampoEntrada rotulo="Ativo (código)" value={f.ativo_codigo} list="ativos-do-responsavel"
        placeholder="ex.: B1" onChange={(e) => setF({ ...f, ativo_codigo: e.target.value })}
        dica="A pessoa responde por uma unidade ou por um ativo." />
      <datalist id="ativos-do-responsavel">
        {codigos.map((c) => <option key={c} value={c} />)}
      </datalist>
      <CampoEntrada rotulo="Consentimento (LGPD)" className="sm:col-span-2" value={f.consentimento}
        placeholder="para o que a pessoa consentiu" onChange={(e) => setF({ ...f, consentimento: e.target.value })}
        dica="Só para empreendedor pessoa física: para o que a pessoa consentiu ao informar os próprios dados. Vazio: não se aplica." />
      {unidades.error && <Aviso tipo="erro" className="sm:col-span-2">{mensagem(unidades.error)}.</Aviso>}
      {unidades.data && !listaUnidades.length && (
        <p className="text-[13px] text-texto-2 sm:col-span-2">
          Nenhuma unidade cadastrada ainda: crie a unidade abaixo antes de registrar o responsável.
        </p>
      )}
      {criar.error && <Aviso tipo="erro" className="sm:col-span-2">{mensagem(criar.error)}.</Aviso>}
      <div className="sm:col-span-2">
        <Botao type="submit" variante="primario" icone={<UserPlus className="size-4" />} carregando={criar.isPending}
          disabled={!f.nome.trim() || !escolhido || (!f.unidade && !f.ativo_codigo.trim())}>
          Cadastrar responsável
        </Botao>
      </div>
      <p className="text-xs text-texto-3 sm:col-span-2">
        Ver o CPF inteiro é do Regulatório, da Diretoria e da TI da empresa; cada visualização fica na auditoria. O CPF nunca vai para a IA.
      </p>
    </form>
  );
}

// ------------------------------------------------------------------ seção: responsáveis

export function SecaoResponsaveis() {
  const t = useTorre();
  const responsaveis = useResponsaveis();
  const lista = responsaveis.data ?? [];

  return (
    <Secao
      titulo="Responsáveis técnicos"
      descricao="Quem assina tecnicamente pela operação, com registro no conselho e ART. O CPF aparece sempre mascarado."
    >
      {responsaveis.isLoading && <Carregando linhas={3} />}
      {responsaveis.error && <ErroCarga erro={responsaveis.error} onTentar={() => responsaveis.refetch()} />}
      {responsaveis.data && !lista.length && (
        <Vazio icone={<UserPlus className="size-4" />}>Nenhum responsável técnico cadastrado ainda.</Vazio>
      )}
      {lista.length > 0 && (
        <>
          <p className="mb-2 text-xs text-texto-2">{plural(lista.length, "responsável", "responsáveis")}</p>
          <ul className="grid gap-3 md:grid-cols-2" data-testid="responsaveis">
            {lista.map((r) => <CartaoResponsavel key={r.id} r={r} />)}
          </ul>
        </>
      )}

      {!t.soLeitura && !t.ti && (
        <Cartao className="mt-4 p-4 sm:p-5">
          <p className="text-sm font-semibold">Novo responsável técnico</p>
          <p className="mt-0.5 text-xs text-texto-2">
            A pessoa responde por uma unidade ou por um ativo. O CPF entra cifrado e nunca volta inteiro na lista.
          </p>
          <div className="mt-3"><FormResponsavel /></div>
        </Cartao>
      )}
    </Secao>
  );
}

// ------------------------------------------------------------------ seção: unidades

function FormUnidade() {
  const t = useTorre();
  const id = t.empresa?.id ?? 0;
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const vazio = { nome: "", uf: "", municipio: "" };
  const [f, setF] = useState(vazio);
  const criar = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/empresas/{empresa_id}/unidades", {
      params: { path: { empresa_id: id } },
      body: { nome: f.nome.trim(), uf: f.uf.trim() || null, municipio: f.municipio.trim() || null },
    })),
    onSuccess: () => {
      avisar(`Unidade ${f.nome.trim()} criada`);
      setF(vazio);
      invalidar();
    },
  });

  return (
    <form className="grid gap-3 sm:grid-cols-[2fr_80px_2fr]" data-testid="form-unidade" onSubmit={(e) => { e.preventDefault(); criar.mutate(); }}>
      <CampoEntrada rotulo="Nome da unidade" required value={f.nome} placeholder="ex.: Mina Serra Azul"
        onChange={(e) => setF({ ...f, nome: e.target.value })} />
      <CampoEntrada rotulo="UF" value={f.uf} maxLength={2} placeholder="MG"
        onChange={(e) => setF({ ...f, uf: e.target.value })} />
      <CampoEntrada rotulo="Município" value={f.municipio} placeholder="ex.: Itabirito"
        onChange={(e) => setF({ ...f, municipio: e.target.value })} />
      {criar.error && <Aviso tipo="erro" className="sm:col-span-3">{mensagem(criar.error)}.</Aviso>}
      <div className="sm:col-span-3">
        <Botao type="submit" variante="primario" icone={<Factory className="size-4" />} carregando={criar.isPending}
          disabled={!f.nome.trim()}>
          Criar unidade
        </Botao>
      </div>
    </form>
  );
}

export function SecaoUnidades() {
  const t = useTorre();
  const unidades = useUnidades();
  const lista = unidades.data ?? [];

  return (
    <Secao titulo="Unidades" descricao="As operações da empresa e os ativos de cada uma. O ativo herda a unidade a que pertence.">
      {t.ti && (
        <Aviso tipo="info">A TI administra contas e não vê o dado regulatório da empresa.</Aviso>
      )}

      {!t.ti && unidades.isLoading && <Carregando linhas={2} />}
      {!t.ti && unidades.error && <ErroCarga erro={unidades.error} onTentar={() => unidades.refetch()} />}
      {!t.ti && unidades.data && !lista.length && (
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

      {!t.soLeitura && !t.ti && (
        <Cartao className="mt-4 p-4 sm:p-5">
          <p className="text-sm font-semibold">Nova unidade</p>
          <p className="mt-0.5 text-xs text-texto-2">A operação que agrupa barragens e equipamentos. O nome é único na empresa.</p>
          <div className="mt-3"><FormUnidade /></div>
        </Cartao>
      )}
    </Secao>
  );
}
