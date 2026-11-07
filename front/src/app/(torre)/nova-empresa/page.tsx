"use client";

// Nova empresa (curadoria da Mitra): criar a instanciação, trazer as barragens do SIGBM e abrir a
// primeira conta da cliente. O resto é da própria empresa — nos dados operacionais a plataforma só
// lê —, e o acompanhamento das oito etapas fica na tela Instanciação, empresa a empresa.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, KeyRound, Plus, Waves } from "lucide-react";
import Link from "next/link";
import { useId, useState } from "react";
import { useAvisar } from "@/components/avisos";
import { Dialogo } from "@/components/dialogo";
import {
  Aviso, Botao, CampoEntrada, Carregando, Cartao, ErroCarga, Etiqueta, Secao, Titulo, Vazio,
  classeBotao, cx, mensagem,
} from "@/components/ui";
import { ErroApi, api, dados } from "@/lib/api";
import { dataBR, plural } from "@/lib/formato";
import { cnpjBR, etapasProntas, ufsDeTexto, type EstadoInstanciacao } from "@/lib/instanciacao";
import { useTorre } from "@/lib/torre";

function useInstanciacoes(ligada: boolean) {
  return useQuery({
    queryKey: ["instanciacoes"],
    queryFn: () => dados(api.GET("/api/v1/instanciacoes")),
    enabled: ligada,
  });
}

function useInvalidarInstanciacoes() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["instanciacoes"] }),
      qc.invalidateQueries({ queryKey: ["empresas"] }),
      qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "torre" }),
    ]);
}

// ------------------------------------------------------------------ criar a empresa

function CriarEmpresa() {
  const avisar = useAvisar();
  const invalidar = useInvalidarInstanciacoes();
  const [nome, setNome] = useState("");
  const [razao, setRazao] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [ufsTexto, setUfsTexto] = useState("");
  const [ficticia, setFicticia] = useState(false);
  const idFicticia = useId();
  const ufs = ufsDeTexto(ufsTexto);

  const criar = useMutation({
    mutationFn: () =>
      dados(api.POST("/api/v1/instanciacoes", {
        body: { nome: nome.trim(), razao_social: razao.trim(), cnpj: cnpj.trim() || null, ufs: ufs.ufs, ficticia },
      })),
    onSuccess: async (r) => {
      await invalidar();
      avisar(`Empresa criada: ${r.estado.empresa}. Agora as barragens do SIGBM e a primeira conta.`);
      setNome(""); setRazao(""); setCnpj(""); setUfsTexto(""); setFicticia(false);
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });

  const pronto = nome.trim().length >= 2 && razao.trim().length >= 2 && !ufs.erro;

  return (
    <Cartao className="p-4 sm:p-5">
      <form
        className="grid gap-3 sm:grid-cols-2"
        data-testid="criar-empresa"
        onSubmit={(e) => { e.preventDefault(); if (pronto) criar.mutate(); }}
      >
        <CampoEntrada rotulo="Nome na torre" value={nome} onChange={(e) => setNome(e.target.value)}
          placeholder="Mineradora Nova" required minLength={2} />
        <CampoEntrada rotulo="Razão social" value={razao} onChange={(e) => setRazao(e.target.value)}
          placeholder="Mineradora Nova S.A." required minLength={2} />
        <CampoEntrada rotulo="CNPJ" value={cnpj} onChange={(e) => setCnpj(e.target.value)}
          placeholder="11.222.333/0001-81" dica="Vazio: empreendedor pessoa física, sem busca no SIGBM." />
        <CampoEntrada rotulo="UFs em que opera" value={ufsTexto} onChange={(e) => setUfsTexto(e.target.value)}
          placeholder="MG, PR" dica={ufs.erro ?? "Separe por vírgula ou espaço. UF nova sem conector vira lacuna declarada na cobertura."} />
        <div className="flex items-center gap-2 sm:col-span-2">
          <input id={idFicticia} type="checkbox" checked={ficticia} onChange={(e) => setFicticia(e.target.checked)}
            className="size-4 accent-marca" />
          <label htmlFor={idFicticia} className="text-sm text-texto-2">Empresa de demonstração (fictícia)</label>
        </div>
        <div className="sm:col-span-2">
          <Botao type="submit" variante="primario" icone={<Plus className="size-4" />}
            disabled={!pronto} carregando={criar.isPending}>
            Criar a empresa
          </Botao>
        </div>
      </form>
      {ufs.erro && <Aviso tipo="erro" className="mt-3">{ufs.erro}</Aviso>}
    </Cartao>
  );
}

// ------------------------------------------------------------------ barragens do SIGBM

function DialogoSigbm({ estado, onFechar }: { estado: EstadoInstanciacao; onFechar: () => void }) {
  const avisar = useAvisar();
  const invalidar = useInvalidarInstanciacoes();
  const [escolhidas, setEscolhidas] = useState<Set<string>>(new Set());
  const busca = useQuery({
    queryKey: ["instanciacao-sigbm", estado.cnpj],
    queryFn: () => dados(api.GET("/api/v1/instanciacoes/sigbm", { params: { query: { cnpj: estado.cnpj ?? "" } } })),
    retry: false,
  });
  const semBarragem = busca.error instanceof ErroApi && busca.error.status === 404;

  const importar = useMutation({
    mutationFn: () =>
      dados(api.POST("/api/v1/empresas/{empresa_id}/instanciacao/sigbm", {
        params: { path: { empresa_id: estado.empresa_id } },
        body: { codigos: [...escolhidas] },
      })),
    onSuccess: async () => {
      await invalidar();
      avisar(`${plural(escolhidas.size, "barragem trazida", "barragens trazidas")} do SIGBM para ${estado.empresa}.`);
      onFechar();
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });

  function alternar(codigo: string) {
    setEscolhidas((s) => {
      const novo = new Set(s);
      if (novo.has(codigo)) novo.delete(codigo);
      else novo.add(codigo);
      return novo;
    });
  }

  return (
    <Dialogo aberto onFechar={onFechar} titulo={`Barragens do SIGBM · ${estado.empresa}`} largura="lg"
      rodape={<>
        <Botao onClick={onFechar}>Cancelar</Botao>
        <Botao variante="primario" disabled={!escolhidas.size} carregando={importar.isPending}
          onClick={() => importar.mutate()}>
          {escolhidas.size ? `Trazer ${plural(escolhidas.size, "barragem", "barragens")}` : "Escolha as barragens"}
        </Botao>
      </>}>
      <p className="text-sm text-texto-2">
        Todas as barragens do CNPJ {cnpjBR(estado.cnpj)} no SIGBM público, não só as da PNSB. A curadoria escolhe
        quais entram; o que o SIGBM não informa fica como dado faltando, para a empresa preencher.
      </p>
      {busca.isLoading && <Carregando className="mt-3" linhas={3} />}
      {semBarragem && <Aviso tipo="info" className="mt-3">CNPJ não encontrado no SIGBM público: a empresa entra só com CNPJ e nome.</Aviso>}
      {busca.error && !semBarragem && <div className="mt-3"><ErroCarga erro={busca.error} onTentar={() => busca.refetch()} /></div>}
      {busca.data && (
        <ul className="mt-3 space-y-2" data-testid="sigbm-barragens">
          {busca.data.barragens.map((b) => (
            <li key={b.codigo}>
              <label className={cx("flex cursor-pointer items-start gap-2.5 rounded-md border px-3 py-2.5",
                escolhidas.has(b.codigo) ? "border-marca bg-marca-suave/40" : "border-borda")}>
                <input type="checkbox" className="mt-0.5 size-4 accent-marca" checked={escolhidas.has(b.codigo)}
                  onChange={() => alternar(b.codigo)} />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold">{b.nome}</span>
                    <Etiqueta tom="neutro">SIGBM {b.codigo}</Etiqueta>
                    {b.na_pnsb && <Etiqueta tom="marca">PNSB</Etiqueta>}
                  </span>
                  <span className="block text-[13px] text-texto-2">
                    {[b.municipio, b.uf].filter(Boolean).join(" · ") || "sem município e UF no SIGBM"}
                  </span>
                  {b.alertas.length > 0 && (
                    <span className="mt-1 flex flex-wrap gap-1">
                      {b.alertas.map((a) => <Etiqueta key={a} tom="atencao">{a}</Etiqueta>)}
                    </span>
                  )}
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </Dialogo>
  );
}

// ------------------------------------------------------------------ a primeira conta

function DialogoPrimeiraConta({ estado, onFechar }: { estado: EstadoInstanciacao; onFechar: () => void }) {
  const avisar = useAvisar();
  const invalidar = useInvalidarInstanciacoes();
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");

  const criar = useMutation({
    mutationFn: () =>
      dados(api.POST("/api/v1/empresas/{empresa_id}/instanciacao/primeira-conta", {
        params: { path: { empresa_id: estado.empresa_id } },
        body: { email: email.trim(), nome: nome.trim(), senha_provisoria: senha },
      })),
    onSuccess: async (r) => {
      await invalidar();
      avisar(`Conta de ${r.email} criada com senha provisória: a pessoa troca no primeiro acesso.`);
      onFechar();
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });

  const pronto = email.includes("@") && nome.trim().length >= 2 && senha.length >= 8;

  return (
    <Dialogo aberto onFechar={onFechar} titulo={`Primeira conta · ${estado.empresa}`}
      rodape={<>
        <Botao onClick={onFechar}>Cancelar</Botao>
        <Botao variante="primario" disabled={!pronto} carregando={criar.isPending} onClick={() => criar.mutate()}>
          Criar a conta da TI
        </Botao>
      </>}>
      <p className="text-sm text-texto-2">
        Só a primeira conta é da curadoria — vai para a TI da empresa, com senha provisória. Daí em diante é a
        própria TI que cria as demais, com escopo por unidade.
      </p>
      <form className="mt-4 grid gap-3" onSubmit={(e) => { e.preventDefault(); if (pronto) criar.mutate(); }}>
        <CampoEntrada rotulo="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="ti@mineradora.example" required />
        <CampoEntrada rotulo="Nome" value={nome} onChange={(e) => setNome(e.target.value)} required minLength={2} />
        <CampoEntrada rotulo="Senha provisória" type="password" value={senha} onChange={(e) => setSenha(e.target.value)}
          dica="A pessoa troca no primeiro acesso; a torre não libera antes." required minLength={8} />
      </form>
    </Dialogo>
  );
}

// ------------------------------------------------------------------ a lista

function CartaoInstanciacao({ estado, onSigbm, onConta }:
  { estado: EstadoInstanciacao; onSigbm: () => void; onConta: () => void }) {
  const { setEmpresaId } = useTorre();
  const { prontas, total } = etapasProntas(estado);
  return (
    <Cartao className="flex h-full flex-col p-4" data-testid="instanciacao-cartao">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{estado.empresa}</p>
          <p className="text-[13px] text-texto-2">{estado.razao_social}</p>
          <p className="num mt-0.5 text-xs text-texto-3">CNPJ {cnpjBR(estado.cnpj)}
            {estado.ufs.length ? ` · ${estado.ufs.join(", ")}` : ""}</p>
        </div>
        {estado.em_operacao
          ? <Etiqueta tom="ok">em operação desde {dataBR(estado.monitorado_desde)}</Etiqueta>
          : <Etiqueta tom="atencao">instanciando</Etiqueta>}
      </div>

      <div className="mt-3">
        <div className="flex items-baseline justify-between text-[13px]">
          <span className="text-texto-2">{prontas} de {total} etapas prontas</span>
          <span className="num font-semibold">{estado.percentual}%</span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-fundo-3" role="progressbar"
          aria-label={`Instanciação de ${estado.empresa}`} aria-valuemin={0} aria-valuemax={100}
          aria-valuenow={estado.percentual}>
          <div className={cx("h-full rounded-full", estado.percentual === 100 ? "bg-emdia" : "bg-marca")}
            style={{ width: `${estado.percentual}%` }} />
        </div>
      </div>

      <div className="mt-auto flex flex-wrap gap-2 pt-3.5">
        <Link href="/instanciacao/" onClick={() => setEmpresaId(estado.empresa_id)} className={classeBotao("secundario", "p")}>
          Acompanhar as etapas
        </Link>
        {estado.cnpj && (
          <Botao tamanho="p" icone={<Waves className="size-3.5" />} onClick={onSigbm}>Barragens do SIGBM</Botao>
        )}
        <Botao tamanho="p" icone={<KeyRound className="size-3.5" />} onClick={onConta}>Primeira conta</Botao>
      </div>
    </Cartao>
  );
}

export default function NovaEmpresa() {
  const t = useTorre();
  const lista = useInstanciacoes(t.plataforma);
  const [sigbm, setSigbm] = useState<EstadoInstanciacao | null>(null);
  const [conta, setConta] = useState<EstadoInstanciacao | null>(null);

  if (!t.plataforma) {
    return (
      <Aviso tipo="info">
        Levar uma empresa nova para dentro é trabalho da curadoria da Mitra. A instanciação da sua empresa
        está em <Link className="font-semibold underline" href="/instanciacao/">Instanciação</Link>.
      </Aviso>
    );
  }

  return (
    <>
      <Titulo sobre="Curadoria Mitra" titulo="Nova empresa">
        Do contrato à torre no ar: a curadoria cria a empresa, traz as barragens do SIGBM e abre a primeira conta.
        O resto — ativos, licenças, responsáveis — é da própria empresa: nos dados operacionais a plataforma só lê.
      </Titulo>

      <Secao titulo="Criar a empresa" descricao="Etapa 1 do roteiro: CNPJ, razão social e as UFs em que opera.">
        <CriarEmpresa />
      </Secao>

      <Secao
        titulo="Instanciações"
        descricao="As empresas que entraram (ou estão entrando) pela instanciação, com o andamento das oito etapas."
      >
        {lista.isLoading && <Carregando linhas={3} />}
        {lista.error && <ErroCarga erro={lista.error} onTentar={() => lista.refetch()} />}
        {lista.data && !lista.data.length && (
          <Vazio icone={<Building2 className="size-4" />}>Nenhuma instanciação ainda: crie a primeira empresa acima.</Vazio>
        )}
        {lista.data && lista.data.length > 0 && (
          <ul className="grid gap-3 md:grid-cols-2" data-testid="instanciacoes">
            {lista.data.map((e) => (
              <li key={e.empresa_id}>
                <CartaoInstanciacao estado={e} onSigbm={() => setSigbm(e)} onConta={() => setConta(e)} />
              </li>
            ))}
          </ul>
        )}
      </Secao>

      {sigbm && <DialogoSigbm estado={sigbm} onFechar={() => setSigbm(null)} />}
      {conta && <DialogoPrimeiraConta estado={conta} onFechar={() => setConta(null)} />}
    </>
  );
}
