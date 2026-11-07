"use client";

// As licenças da empresa: o PDF enviado, a leitura da IA (cada condicionante com o trecho literal e a página
// do PDF, conferidos pelo Python) e a decisão de quem é da empresa — aprovar, corrigir e aprovar, ou rejeitar.
// Aprovada, a condicionante vira obrigação própria, com código, e a torre passa a cobrá-la. A plataforma só
// lê: na visão da Mitra não há envio, leitura nem decisão.
import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarClock, FileUp, ScanText } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useAvisar } from "@/components/avisos";
import { CartaoCondicionante, type Condicionante, type Decisao } from "@/components/condicionantes";
import {
  Abas, Aviso, Botao, Campo, CampoEntrada, CampoSelecao, Carregando, Cartao, Entrada, ErroCarga, Etiqueta,
  Secao, Titulo, Vazio, cx, mensagem,
} from "@/components/ui";
import { api, dados, enviarArquivo, type Esquemas } from "@/lib/api";
import { useAtivos, useInvalidarTorre } from "@/lib/consultas";
import { dataBR, emBrasilia, maiuscula, plural, usd } from "@/lib/formato";
import { useEmpresa, useTorre } from "@/lib/torre";

type Licenca = Esquemas["Licenca"];
type Leitura = Esquemas["api__rotas__licencas__Leitura"];

const TIPOS = ["LP", "LI", "LO", "LAC", "outorga", "autorizacao"] as const;
const RENOVAR_PADRAO = 120;

const ABAS = [
  { id: "pendente", rotulo: "Pendentes" },
  { id: "aprovada", rotulo: "Aprovadas" },
  { id: "rejeitada", rotulo: "Rejeitadas" },
  { id: "todas", rotulo: "Todas" },
] as const;
type Filtro = (typeof ABAS)[number]["id"];

const VAZIO: Record<Filtro, string> = {
  pendente: "Nenhuma condicionante esperando decisão. Envie o PDF de uma licença e mande ler.",
  aprovada: "Nenhuma condicionante aprovada ainda.",
  rejeitada: "Nenhuma condicionante rejeitada.",
  todas: "Nenhuma condicionante ainda: envie o PDF de uma licença e mande ler.",
};

// ------------------------------------------------------------------ consultas

function useLicencas() {
  const { empresa, chave } = useTorre();
  const id = empresa?.id ?? 0;
  return useQuery({
    queryKey: [...chave, "licencas"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/licencas", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
}

function useCondicionantes() {
  const { empresa, chave } = useTorre();
  const id = empresa?.id ?? 0;
  return useQuery({
    queryKey: [...chave, "condicionantes"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/condicionantes", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
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

// ------------------------------------------------------------------ envio do PDF

type Form = { tipo: string; numero: string; orgao: string; emitida_em: string; validade: string; renovar_dias: string; unidade: string; ativo_codigo: string };
const FORM_VAZIO: Form = { tipo: "", numero: "", orgao: "", emitida_em: "", validade: "", renovar_dias: String(RENOVAR_PADRAO), unidade: "", ativo_codigo: "" };

function EnviarLicenca({ onEnviada }: { onEnviada: (l: Licenca) => void }) {
  const empresa = useEmpresa();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const unidades = useUnidades();
  const ativos = useAtivos();
  const arquivoRef = useRef<HTMLInputElement>(null);
  const [f, setF] = useState<Form>(FORM_VAZIO);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const dias = Number(f.renovar_dias);

  const enviar = useMutation({
    mutationFn: () => enviarArquivo<Licenca>(`/api/v1/empresas/${empresa.id}/licencas`, {
      tipo: f.tipo,
      numero: f.numero.trim(),
      orgao: f.orgao.trim() || null,
      emitida_em: f.emitida_em || null,
      validade: f.validade || null,
      renovar_dias: Number.isFinite(dias) && dias > 0 ? dias : RENOVAR_PADRAO,
      unidade: f.unidade.trim() || null,
      ativo_codigo: f.ativo_codigo.trim() || null,
    }, arquivo!),
    onSuccess: (l) => {
      avisar(`Licença ${l.tipo} ${l.numero} guardada. Agora mande ler: a IA propõe as condicionantes e o Python confere o trecho.`);
      setF(FORM_VAZIO);
      setArquivo(null);
      if (arquivoRef.current) arquivoRef.current.value = "";
      onEnviada(l);
      return invalidar();
    },
    onError: (e) => avisar(`Licença não aceita: ${mensagem(e)}`, "erro"),
  });

  return (
    <div className="rounded-lg border border-dashed border-borda-forte bg-fundo p-4" data-testid="enviar-licenca">
      <div className="flex items-center gap-2">
        <FileUp className="size-4 text-marca" aria-hidden />
        <h2 className="text-base font-semibold">Chegou uma licença nova?</h2>
      </div>
      <p className="mt-1 text-[13px] text-texto-2">
        Mande o PDF e o que identifica a licença. O texto fica guardado para o Python conferir cada condicionante
        palavra por palavra; nada vira obrigação antes de alguém da empresa aprovar.
      </p>
      <form className="mt-3 space-y-3" onSubmit={(e) => { e.preventDefault(); enviar.mutate(); }}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <CampoSelecao rotulo="Tipo" value={f.tipo} required onChange={(e) => setF((x) => ({ ...x, tipo: e.target.value }))}>
            <option value="">—</option>
            {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
          </CampoSelecao>
          <CampoEntrada rotulo="Número" value={f.numero} required maxLength={60} placeholder="ex.: 123/2026"
            onChange={(e) => setF((x) => ({ ...x, numero: e.target.value }))} />
          <CampoEntrada rotulo="Órgão emissor" value={f.orgao} maxLength={200} placeholder="ex.: SEMAD-MG"
            onChange={(e) => setF((x) => ({ ...x, orgao: e.target.value }))} />
          <CampoEntrada rotulo="Renovar com" type="number" min={1} max={1095} value={f.renovar_dias}
            dica="dias antes do vencimento" onChange={(e) => setF((x) => ({ ...x, renovar_dias: e.target.value }))} />
          <CampoEntrada rotulo="Emitida em" type="date" value={f.emitida_em}
            onChange={(e) => setF((x) => ({ ...x, emitida_em: e.target.value }))} />
          <CampoEntrada rotulo="Validade" type="date" value={f.validade} dica="vira a obrigação de renovar"
            onChange={(e) => setF((x) => ({ ...x, validade: e.target.value }))} />
          <Campo rotulo="Unidade" dica="se a licença é de uma unidade">
            <Entrada list="unidades-da-empresa" value={f.unidade} placeholder="nome da unidade"
              onChange={(e) => setF((x) => ({ ...x, unidade: e.target.value }))} />
            <datalist id="unidades-da-empresa">
              {(unidades.data ?? []).map((u) => <option key={u.id} value={u.nome} />)}
            </datalist>
          </Campo>
          <Campo rotulo="Ativo" dica="se a licença é de um ativo">
            <Entrada list="ativos-da-empresa" value={f.ativo_codigo} placeholder="código do ativo"
              onChange={(e) => setF((x) => ({ ...x, ativo_codigo: e.target.value }))} />
            <datalist id="ativos-da-empresa">
              {(ativos.data ?? []).map((a) => <option key={a.codigo} value={a.codigo}>{a.nome}</option>)}
            </datalist>
          </Campo>
        </div>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <Campo rotulo="PDF da licença" htmlFor="arquivo-licenca" dica="Até 20 MB. Se o PDF for escaneado, mande a versão digital.">
            <input ref={arquivoRef} id="arquivo-licenca" type="file" accept="application/pdf,.pdf"
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="text-sm file:mr-3 file:rounded-md file:border file:border-borda-forte file:bg-fundo file:px-3 file:py-1.5 file:text-sm file:text-texto" />
          </Campo>
          <Botao type="submit" variante="primario" carregando={enviar.isPending}
            disabled={!arquivo || !f.tipo || !f.numero.trim()}>
            Enviar licença
          </Botao>
        </div>
      </form>
    </div>
  );
}

// ------------------------------------------------------------------ as licenças

function CartaoLicenca({ l, destaque, podeLer, podeRenovar, lendo, renovando, onLer, onRenovar }: {
  l: Licenca;
  destaque: boolean;
  podeLer: boolean;
  podeRenovar: boolean;
  lendo: boolean;
  renovando: boolean;
  onLer: () => void;
  onRenovar: () => void;
}) {
  const ocupado = lendo || renovando;
  const c = l.condicionantes;

  return (
    <Cartao id={`licenca-${l.id}`} className={cx("p-4 sm:p-5", destaque && "border-marca")} data-testid="licenca">
      <div className="flex flex-wrap items-center gap-2">
        <Etiqueta tom="marca">{l.tipo}</Etiqueta>
        <h2 className="text-base font-semibold">{l.numero}</h2>
        {l.orgao && <span className="text-[13px] text-texto-2">{l.orgao}</span>}
      </div>

      <p className="mt-1 text-[13px] text-texto-2">
        {l.emitida_em ? `Emitida em ${dataBR(l.emitida_em)}` : "Data de emissão não informada"}
        {l.validade
          ? ` · vale até ${dataBR(l.validade)}, renovar ${plural(l.renovar_dias, "dia", "dias")} antes`
          : " · sem validade no cadastro"}
        {l.unidade ? ` · unidade ${l.unidade}` : ""}
        {l.ativo_codigo ? ` · ativo ${l.ativo_codigo}` : ""}
      </p>
      <p className="mt-0.5 text-xs text-texto-3">
        {l.arquivo ?? "sem PDF guardado"}
        {l.sha256 ? ` · sha256 ${l.sha256.slice(0, 12)}…` : ""}
        {` · enviada por ${l.enviada_por} em ${emBrasilia(l.enviada_em)}`}
      </p>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {!!c.pendente && <Etiqueta tom="proposta">{plural(c.pendente, "pendente", "pendentes")}</Etiqueta>}
        {!!c.aprovada && <Etiqueta tom="ok">{plural(c.aprovada, "aprovada", "aprovadas")}</Etiqueta>}
        {!!c.rejeitada && <Etiqueta tom="perigo">{plural(c.rejeitada, "rejeitada", "rejeitadas")}</Etiqueta>}
        {!c.pendente && !c.aprovada && !c.rejeitada && (
          <span className="text-[13px] text-texto-3">Nenhuma condicionante lida ainda.</span>
        )}
      </div>

      {(podeLer || podeRenovar) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {podeLer && (
            <Botao tamanho="p" icone={<ScanText className="size-3.5" aria-hidden />} carregando={lendo} disabled={ocupado}
              title={c.pendente ? "Ler de novo propõe outra vez; as pendentes continuam até alguém decidir" : "A IA propõe as condicionantes e o Python confere o trecho"}
              onClick={onLer}>
              {c.pendente ? "Ler de novo" : "Ler a licença"}
            </Botao>
          )}
          {podeRenovar && l.validade && (
            <Botao tamanho="p" icone={<CalendarClock className="size-3.5" aria-hidden />} carregando={renovando} disabled={ocupado}
              title={`A torre cobra o pedido de renovação ${l.renovar_dias} dias antes de ${dataBR(l.validade)}`}
              onClick={onRenovar}>
              Criar a obrigação de renovar
            </Botao>
          )}
          {podeRenovar && !l.validade && (
            <span className="self-center text-xs text-texto-3">Sem validade no cadastro: não há renovação a cobrar.</span>
          )}
        </div>
      )}
    </Cartao>
  );
}

// ------------------------------------------------------------------ a leitura

function ResultadoLeitura({ l, r }: { l: Licenca; r: Leitura }) {
  const validadeDiferente = !!r.validade_lida && r.validade_lida !== (l.validade ?? "");
  const propostas = r.propostas.length;

  return (
    <Cartao className="p-4 sm:p-5" data-testid="leitura-licenca">
      <div className="flex flex-wrap items-center gap-2">
        <Etiqueta tom="marca">{l.tipo} {l.numero}</Etiqueta>
        <h2 className="text-base font-semibold">O que a leitura achou</h2>
      </div>
      <p className="mt-0.5 text-[13px] text-texto-2">
        {r.modelo ? `Leitura do modelo ${r.modelo}` : "Leitura da IA"}
        {r.custo_usd > 0 ? ` · custo ${usd(r.custo_usd)}` : " · sem custo"}
        {" "}· o Python confere cada trecho palavra por palavra antes de aceitar.
      </p>

      <dl className="mt-3 grid gap-x-6 gap-y-2 rounded-md bg-fundo-2 px-4 py-3 text-[13px] sm:grid-cols-3">
        <div>
          <dt className="text-xs text-texto-3">Validade lida no PDF</dt>
          <dd className="font-medium">{dataBR(r.validade_lida)}</dd>
        </div>
        <div>
          <dt className="text-xs text-texto-3">Número lido no PDF</dt>
          <dd className="font-medium">{r.numero_lido ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-texto-3">Órgão lido no PDF</dt>
          <dd className="font-medium">{r.orgao_lido ?? "—"}</dd>
        </div>
      </dl>

      {validadeDiferente && (
        <Aviso tipo="atencao" className="mt-3">
          A IA leu a validade <strong>{dataBR(r.validade_lida)}</strong> no PDF, mas o cadastro desta licença diz{" "}
          <strong>{l.validade ? dataBR(l.validade) : "sem validade"}</strong>. A renovação é cobrada pela data do cadastro:
          confira antes de aprovar as condicionantes.
        </Aviso>
      )}

      {r.problemas.map((p) => (
        <Aviso key={p} tipo="atencao" className="mt-3">{maiuscula(p)}</Aviso>
      ))}

      {r.reprovadas.length > 0 && (
        <div className="mt-3 rounded-md border border-atrasada/40 bg-atrasada-fundo px-4 py-3" data-testid="reprovadas">
          <p className="text-sm font-semibold">
            O Python recusou {plural(r.reprovadas.length, "proposta da IA", "propostas da IA")}: nenhuma entra
          </p>
          <ul className="mt-1.5 space-y-1 text-[13px]">
            {r.reprovadas.map((x, i) => (
              <li key={`${x.titulo}-${i}`}>
                <strong>{x.titulo || "sem título"}</strong>: {x.motivo}.
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-xs">
            Sem o trecho literal conferido no texto do PDF, a proposta não vira condicionante — e nada disso foi gravado.
          </p>
        </div>
      )}

      <p className="mt-3 text-sm">
        {propostas > 0 ? (
          <>
            A conferência aceitou {plural(propostas, "proposta", "propostas")}: {propostas === 1 ? "ela está" : "elas estão"} pendente
            {propostas === 1 ? "" : "s"} de decisão em{" "}
            <a href="#condicionantes" className="font-medium text-marca hover:underline">Condicionantes</a>.
          </>
        ) : "Nenhuma proposta passou na conferência."}
      </p>
    </Cartao>
  );
}

// ------------------------------------------------------------------ a decisão

function ListaCondicionantes({ onDecidida }: { onDecidida: (c: Condicionante, d: Decisao) => void }) {
  const lista = useCondicionantes();
  const [filtro, setFiltro] = useState<Filtro>("pendente");
  const todas = useMemo(() => lista.data ?? [], [lista.data]);
  const contagem: Record<Filtro, number> = {
    pendente: todas.filter((c) => c.status === "pendente").length,
    aprovada: todas.filter((c) => c.status === "aprovada").length,
    rejeitada: todas.filter((c) => c.status === "rejeitada").length,
    todas: todas.length,
  };
  const mostradas = filtro === "todas" ? todas : todas.filter((c) => c.status === filtro);

  if (lista.isLoading) return <Carregando linhas={3} />;
  if (lista.error) return <ErroCarga erro={lista.error} onTentar={() => lista.refetch()} />;

  return (
    <>
      <Abas<Filtro> rotulo="Status das condicionantes" ativa={filtro} onTrocar={setFiltro}
        abas={ABAS.map((a) => ({
          id: a.id,
          rotulo: <>{a.rotulo} <span className="text-texto-3">{contagem[a.id]}</span></>,
        }))} />

      <div className="mt-4 space-y-3">
        {mostradas.length === 0
          ? <Vazio>{VAZIO[filtro]}</Vazio>
          : mostradas.map((c) => <CartaoCondicionante key={c.id} c={c} onDecidida={onDecidida} />)}
      </div>
    </>
  );
}

// ------------------------------------------------------------------ tela

export default function Licencas() {
  const t = useTorre();
  const empresa = useEmpresa();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const licencas = useLicencas();
  const [destaque, setDestaque] = useState<number | null>(null);
  // guardam a empresa: trocar de cliente não deixa a leitura (nem o código) de outra na tela
  const [resultado, setResultado] = useState<{ empresa: number; licenca: Licenca; leitura: Leitura } | null>(null);
  const [ultima, setUltima] = useState<{ empresa: number; titulo: string; codigo: string } | null>(null);

  const ler = useMutation({
    mutationFn: (l: Licenca) => dados(api.POST("/api/v1/licencas/{licenca_id}/leitura", {
      params: { path: { licenca_id: l.id }, query: { empresa_id: empresa.id } },
    })),
    onSuccess: (r, l) => {
      setResultado({ empresa: empresa.id, licenca: l, leitura: r });
      avisar(`${l.tipo} ${l.numero}: ${plural(r.propostas.length, "proposta pendente", "propostas pendentes")}`
        + (r.reprovadas.length ? `, ${plural(r.reprovadas.length, "recusada", "recusadas")} pelo Python` : "") + ".");
      return invalidar();
    },
    onError: (e) => avisar(`Não consegui ler a licença: ${mensagem(e)}`, "erro"),
  });

  const renovar = useMutation({
    mutationFn: (l: Licenca) => dados(api.POST("/api/v1/licencas/{licenca_id}/renovacao", {
      params: { path: { licenca_id: l.id }, query: { empresa_id: empresa.id } },
    })),
    onSuccess: (r, l) => {
      avisar(r.codigo
        ? `Renovação da ${l.tipo} ${l.numero}: a torre cobra pela obrigação ${r.codigo}.`
        : `A ${l.tipo} ${l.numero} não tem validade no cadastro (ou a renovação já existe): nada a cobrar.`);
      return invalidar();
    },
    onError: (e) => avisar(`Não criei a renovação: ${mensagem(e)}`, "erro"),
  });

  // a mais recente primeiro: quem acabou de enviar um PDF acha a licença dele no topo
  const ordenadas = useMemo(
    () => [...(licencas.data ?? [])].sort((a, b) => (b.enviada_em ?? "").localeCompare(a.enviada_em ?? "")),
    [licencas.data],
  );
  const podeEnviar = !t.soLeitura;
  const podeRenovar = t.veTudo && !t.soLeitura;

  return (
    <>
      <Titulo sobre="Regulatório" titulo="Licenças">
        O PDF da licença entra aqui. A IA propõe as condicionantes com o trecho literal, o Python confere palavra por palavra
        e cada proposta só vira obrigação quando alguém da empresa aprova — aprovada, nasce vigente, com código, e a torre
        passa a cobrá-la.
      </Titulo>

      {podeEnviar ? (
        <EnviarLicenca onEnviada={(l) => setDestaque(l.id)} />
      ) : (
        <Aviso tipo="info">
          Visão da plataforma: aqui só se lê. Quem envia o PDF, manda ler e decide cada condicionante é o Regulatório ou a
          Diretoria da própria empresa.
        </Aviso>
      )}

      <Secao titulo="Licenças da empresa"
        descricao="Cada PDF enviado, com a validade que a torre cobra e as condicionantes que já saíram dele.">
        {licencas.isLoading && <Carregando linhas={3} />}
        {licencas.error && <ErroCarga erro={licencas.error} onTentar={() => licencas.refetch()} />}
        {licencas.data && ordenadas.length === 0 && (
          <Vazio icone={<FileUp className="size-4" aria-hidden />}>
            Nenhuma licença enviada ainda.{podeEnviar ? " Envie o PDF acima para começar." : ""}
          </Vazio>
        )}
        <div className="space-y-3">
          {ordenadas.map((l) => (
            <CartaoLicenca key={l.id} l={l} destaque={destaque === l.id}
              podeLer={!t.soLeitura} podeRenovar={podeRenovar}
              lendo={ler.isPending && ler.variables?.id === l.id}
              renovando={renovar.isPending && renovar.variables?.id === l.id}
              onLer={() => ler.mutate(l)} onRenovar={() => renovar.mutate(l)} />
          ))}
        </div>
      </Secao>

      {resultado?.empresa === empresa.id && ordenadas.some((l) => l.id === resultado.licenca.id) && (
        <Secao titulo="Leitura da licença" descricao="O que a IA propôs a partir do texto guardado, e o que o Python recusou.">
          <ResultadoLeitura l={resultado.licenca} r={resultado.leitura} />
        </Secao>
      )}

      <Secao id="condicionantes" titulo="Condicionantes"
        descricao="Cada proposta com o trecho da licença que a sustenta e a página do PDF. Aprovar cria a obrigação; rejeitar tira da lista.">
        {ultima?.empresa === empresa.id && (
          <Aviso tipo="sucesso" className="mb-3">
            Aprovada: “{ultima.titulo}” virou a obrigação <strong>{ultima.codigo}</strong>, já vigente e cobrada pela torre.
          </Aviso>
        )}
        <ListaCondicionantes onDecidida={(c, d) => setUltima(d.codigo
          ? { empresa: empresa.id, titulo: c.titulo, codigo: d.codigo }
          : null)} />
      </Secao>
    </>
  );
}
