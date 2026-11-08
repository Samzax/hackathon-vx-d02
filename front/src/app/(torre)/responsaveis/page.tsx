"use client";

// "Responsáveis e unidades": os responsáveis técnicos com o CPF sempre mascarado (ver o inteiro é
// auditado), as unidades com os ativos de cada uma e as regras próprias da empresa — prazo interno,
// responsável padrão por área e normas internas. Quem muda as regras é o Regulatório ou a Diretoria
// (useTorre().veTudo); o gestor lê, e a plataforma só lê (soLeitura).
import { useMutation, useQuery } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useState } from "react";
import { useAvisar } from "@/components/avisos";
import { SecaoResponsaveis, SecaoUnidades } from "@/components/pessoal";
import {
  Aviso, Botao, Carregando, Cartao, CampoEntrada, CampoSelecao, ErroCarga, Etiqueta, Secao, Titulo, mensagem,
} from "@/components/ui";
import { api, dados, type Esquemas } from "@/lib/api";
import { useInvalidarTorre } from "@/lib/consultas";
import { dataBR, emBrasilia, plural } from "@/lib/formato";
import { TIPO_ATIVO } from "@/lib/status";
import { useTorre } from "@/lib/torre";

type Personalizacao = Esquemas["Personalizacao"];

const areaRotulo = (a: string) => a.replace(/_/g, " ");
const TIPOS = Object.keys(TIPO_ATIVO);

function usePersonalizacao() {
  const { empresa, chave, ti } = useTorre();
  const id = empresa?.id ?? 0;
  return useQuery({
    queryKey: [...chave, "personalizacao"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/personalizacao", { params: { path: { empresa_id: id } } })),
    enabled: !!id && !ti, // a TI administra contas e não vê dado regulatório
    retry: false,
  });
}

// ------------------------------------------------------------------ prazo interno

function PrazosInternos({ p, podeEditar }: { p: Personalizacao; podeEditar: boolean }) {
  const t = useTorre();
  const id = t.empresa?.id ?? 0;
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const [codigo, setCodigo] = useState("");
  const [dias, setDias] = useState("0");
  const valido = !!codigo.trim() && dias !== "" && Number.isInteger(Number(dias)) && Number(dias) >= 0;
  const salvar = useMutation({
    mutationFn: () => dados(api.PUT("/api/v1/empresas/{empresa_id}/prazos-internos", {
      params: { path: { empresa_id: id } },
      body: { codigo: codigo.trim(), dias_antes: Number(dias) },
    })),
    onSuccess: () => {
      const n = Number(dias);
      const c = codigo.trim();
      avisar(n === 0
        ? `Meta de ${c} tirada: a torre volta a cobrar pelo prazo legal`
        : `Prazo interno de ${c}: ${plural(n, "dia", "dias")} antes do prazo legal`);
      setCodigo("");
      setDias("0");
      invalidar();
    },
  });

  return (
    <Cartao className="p-4 sm:p-5">
      <p className="text-sm font-semibold">Prazo interno</p>
      <p className="mt-0.5 text-xs text-texto-2">
        Quantos dias antes do prazo legal a empresa quer entregar. A norma não muda: o prazo legal continua o que ela diz.
      </p>

      {p.prazos_internos.length ? (
        <ul className="mt-3 divide-y divide-borda text-sm" data-testid="prazos-internos">
          {p.prazos_internos.map((x) => (
            <li key={x.codigo} className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5 py-1.5">
              <span className="font-medium">{x.codigo}</span>
              <span className="num text-texto-2">{plural(x.dias_antes, "dia", "dias")} antes</span>
              <span className="text-xs text-texto-3">{x.definido_por} em {emBrasilia(x.definido_em, false)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-[13px] text-texto-2">Nenhum prazo interno: a torre cobra pelo prazo legal.</p>
      )}

      {podeEditar && (
        <form className="mt-4 grid items-end gap-3 sm:grid-cols-[1fr_180px_auto]" data-testid="form-prazo"
          onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
          <CampoEntrada rotulo="Código da obrigação" value={codigo} placeholder="ex.: R95-01" list="codigos-com-prazo"
            onChange={(e) => setCodigo(e.target.value)} dica="O mesmo código que aparece nas entregas." />
          <datalist id="codigos-com-prazo">
            {p.prazos_internos.map((x) => <option key={x.codigo} value={x.codigo} />)}
          </datalist>
          <CampoEntrada rotulo="Dias antes" type="number" min={0} max={365} value={dias}
            onChange={(e) => setDias(e.target.value)} dica="0 tira a meta." />
          <Botao type="submit" icone={<Save className="size-4" />} carregando={salvar.isPending} disabled={!valido}>
            Salvar prazo
          </Botao>
        </form>
      )}
      {salvar.error && <Aviso tipo="erro" className="mt-3">{mensagem(salvar.error)}.</Aviso>}
    </Cartao>
  );
}

// ------------------------------------------------------------------ responsável padrão por área

function ResponsaveisPadrao({ p, podeEditar }: { p: Personalizacao; podeEditar: boolean }) {
  const t = useTorre();
  const id = t.empresa?.id ?? 0;
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const primeira = p.areas[0] ?? "";
  const [area, setArea] = useState(primeira);
  const [responsavel, setResponsavel] = useState(p.responsaveis_padrao[primeira] ?? "");
  const padroes = Object.entries(p.responsaveis_padrao);
  const salvar = useMutation({
    mutationFn: () => dados(api.PUT("/api/v1/empresas/{empresa_id}/responsaveis-padrao", {
      params: { path: { empresa_id: id } },
      body: { area, responsavel: responsavel.trim() },
    })),
    onSuccess: () => {
      const nome = responsavel.trim();
      avisar(nome
        ? `Obrigação nova de ${areaRotulo(area)} passa a ficar com ${nome}`
        : `Padrão de ${areaRotulo(area)} tirado`);
      invalidar();
    },
  });

  return (
    <Cartao className="p-4 sm:p-5">
      <p className="text-sm font-semibold">Responsável padrão por área</p>
      <p className="mt-0.5 text-xs text-texto-2">
        Quem responde por uma obrigação nova de cada área, quando nada foi dito antes.
      </p>

      {padroes.length ? (
        <ul className="mt-3 divide-y divide-borda text-sm" data-testid="responsaveis-padrao">
          {padroes.map(([a, nome]) => (
            <li key={a} className="flex flex-wrap items-baseline justify-between gap-2 py-1.5">
              <Etiqueta tom="neutro">{areaRotulo(a)}</Etiqueta>
              <span>{nome}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-[13px] text-texto-2">Nenhum padrão por área: cada obrigação fica com a área do ativo.</p>
      )}

      {podeEditar && (
        <form className="mt-4 grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]" data-testid="form-padrao"
          onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
          <CampoSelecao rotulo="Área" value={area}
            onChange={(e) => { const a = e.target.value; setArea(a); setResponsavel(p.responsaveis_padrao[a] ?? ""); }}>
            {p.areas.map((a) => <option key={a} value={a}>{areaRotulo(a)}</option>)}
          </CampoSelecao>
          <CampoEntrada rotulo="Responsável" value={responsavel} placeholder="ex.: Gerência de Geotecnia"
            onChange={(e) => setResponsavel(e.target.value)} dica="Vazio tira o padrão desta área." />
          <Botao type="submit" icone={<Save className="size-4" />} carregando={salvar.isPending} disabled={!area}>
            Salvar padrão
          </Botao>
        </form>
      )}
      {salvar.error && <Aviso tipo="erro" className="mt-3">{mensagem(salvar.error)}.</Aviso>}
    </Cartao>
  );
}

// ------------------------------------------------------------------ normas internas

function FormNormaInterna({ p }: { p: Personalizacao }) {
  const t = useTorre();
  const id = t.empresa?.id ?? 0;
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const areaInicial = p.areas.includes("documentacao") ? "documentacao" : (p.areas[0] ?? "documentacao");
  const vazio = {
    titulo: "", tipo_ativo: "barragem", area: areaInicial, agenda: "evento",
    periodicidade: "", prazo: "", evidencia: "", vigencia_desde: "",
  };
  const [f, setF] = useState(vazio);
  const criar = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/empresas/{empresa_id}/normas-internas", {
      params: { path: { empresa_id: id } },
      body: {
        titulo: f.titulo.trim(),
        tipo_ativo: f.tipo_ativo,
        area: f.area,
        agenda: f.agenda.trim() || "evento",
        periodicidade: f.periodicidade.trim() || null,
        prazo: f.prazo.trim() || null,
        evidencia: f.evidencia.trim() || null,
        aplica_se_a: "todos os ativos do tipo",
        regra: "*",
        norma: "Padrão interno",
        vigencia_desde: f.vigencia_desde || null,
      },
    })),
    onSuccess: (d) => {
      avisar(`Norma interna ${d.codigo} criada: a torre passa a cobrar "${f.titulo.trim()}".`);
      setF({ ...vazio });
      invalidar();
    },
  });

  return (
    <form className="mt-4 grid gap-3 sm:grid-cols-2" data-testid="form-norma" onSubmit={(e) => { e.preventDefault(); criar.mutate(); }}>
      <CampoEntrada rotulo="Título" className="sm:col-span-2" required value={f.titulo}
        placeholder="ex.: Inspeção interna mensal da pilha" onChange={(e) => setF({ ...f, titulo: e.target.value })} />
      <CampoSelecao rotulo="Tipo de ativo" value={f.tipo_ativo} onChange={(e) => setF({ ...f, tipo_ativo: e.target.value })}>
        {TIPOS.map((tipo) => <option key={tipo} value={tipo}>{TIPO_ATIVO[tipo]}</option>)}
      </CampoSelecao>
      <CampoSelecao rotulo="Área" value={f.area} onChange={(e) => setF({ ...f, area: e.target.value })}>
        {p.areas.map((a) => <option key={a} value={a}>{areaRotulo(a)}</option>)}
      </CampoSelecao>
      <CampoEntrada rotulo="Agenda" required value={f.agenda} onChange={(e) => setF({ ...f, agenda: e.target.value })}
        dica="A agenda da torre: evento, mensal+10d, anos:3…" />
      <CampoEntrada rotulo="Periodicidade" value={f.periodicidade} placeholder="ex.: Mensal"
        onChange={(e) => setF({ ...f, periodicidade: e.target.value })} />
      <CampoEntrada rotulo="Prazo" value={f.prazo} placeholder="ex.: Até 10 dias após o fim do mês"
        onChange={(e) => setF({ ...f, prazo: e.target.value })} />
      <CampoEntrada rotulo="Evidência" value={f.evidencia} placeholder="ex.: Relatório interno assinado"
        onChange={(e) => setF({ ...f, evidencia: e.target.value })} />
      <CampoEntrada rotulo="A partir de" type="date" value={f.vigencia_desde}
        onChange={(e) => setF({ ...f, vigencia_desde: e.target.value })} dica="Vazio: vale desde já." />
      {criar.error && <Aviso tipo="erro" className="sm:col-span-2">{mensagem(criar.error)}.</Aviso>}
      <div className="sm:col-span-2">
        <Botao type="submit" variante="primario" icone={<Save className="size-4" />} carregando={criar.isPending}
          disabled={f.titulo.trim().length < 3 || !f.agenda.trim()}>
          Criar norma interna
        </Botao>
      </div>
      <p className="text-xs text-texto-3 sm:col-span-2">
        A norma interna é uma obrigação da própria empresa, sem licença: nasce vigente, assinada por quem cadastrou.
      </p>
    </form>
  );
}

function NormasInternas({ p, podeEditar }: { p: Personalizacao; podeEditar: boolean }) {
  return (
    <Cartao className="p-4 sm:p-5">
      <p className="text-sm font-semibold">Normas internas</p>
      <p className="mt-0.5 text-xs text-texto-2">
        As obrigações que a empresa dá a si mesma — padrão corporativo, política interna, TAC — sem depender de licença.
      </p>

      {p.normas_internas.length ? (
        <div className="mt-3 overflow-x-auto rounded-lg border border-borda">
          <table className="w-full min-w-[720px] text-sm" data-testid="normas-internas">
            <thead className="bg-fundo-2 text-left text-xs text-texto-2">
              <tr>
                {["Norma", "Área", "Agenda", "Prazo", "Evidência", "Desde"].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-borda">
              {p.normas_internas.map((n) => (
                <tr key={n.codigo}>
                  <td className="px-3 py-2">
                    <span className="block text-xs text-texto-3">{n.codigo} · {TIPO_ATIVO[n.tipo_ativo] ?? n.tipo_ativo}</span>
                    {n.titulo}
                  </td>
                  <td className="px-3 py-2 text-texto-2">{areaRotulo(n.area)}</td>
                  <td className="px-3 py-2 text-texto-2">{n.agenda ?? "—"}</td>
                  <td className="px-3 py-2 text-texto-2">{n.prazo ?? "—"}</td>
                  <td className="px-3 py-2 text-texto-2">{n.evidencia ?? "—"}</td>
                  <td className="num px-3 py-2 whitespace-nowrap text-texto-2">{dataBR(n.vigencia_desde)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 text-[13px] text-texto-2">Nenhuma norma interna: a torre cobra só o que vem das normas e das licenças.</p>
      )}

      {podeEditar && <FormNormaInterna p={p} />}
    </Cartao>
  );
}

// ------------------------------------------------------------------ seção: regras da empresa

function SecaoRegras() {
  const t = useTorre();
  const personalizacao = usePersonalizacao();
  const podeEditar = t.veTudo && !t.soLeitura && !t.ti;

  return (
    <Secao
      titulo="Regras próprias da empresa"
      descricao={podeEditar
        ? "Como esta empresa organiza o que já vale: a meta interna de prazo, quem responde por área e o que ela cobra de si mesma."
        : "Como esta empresa organiza o que já vale. Quem muda é o Regulatório ou a Diretoria."}
    >
      {personalizacao.isLoading && <Carregando linhas={3} />}
      {personalizacao.error && <ErroCarga erro={personalizacao.error} onTentar={() => personalizacao.refetch()} />}
      {personalizacao.data && (
        <div className="space-y-3">
          <PrazosInternos p={personalizacao.data} podeEditar={podeEditar} />
          <ResponsaveisPadrao p={personalizacao.data} podeEditar={podeEditar} />
          <NormasInternas p={personalizacao.data} podeEditar={podeEditar} />
        </div>
      )}
    </Secao>
  );
}

export default function ResponsaveisEUnidades() {
  const t = useTorre();
  return (
    <>
      <Titulo sobre="Empresa" titulo="Responsáveis e unidades">
        Quem responde tecnicamente pela operação, as unidades com os ativos de cada uma e as regras que a empresa
        dá a si mesma. O CPF aparece sempre mascarado; ver o número inteiro fica registrado na auditoria.
        {t.soLeitura ? " A equipe Mitra acompanha esta tela só para leitura." : ""}
      </Titulo>

      <SecaoResponsaveis />
      <SecaoUnidades />
      {!t.ti && <SecaoRegras />}
    </>
  );
}
