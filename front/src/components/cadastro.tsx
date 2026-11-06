"use client";

import { useMutation } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { api, dados } from "@/lib/api";
import { type Ativo, type CampoCadastro, useCamposCadastro, useInvalidarTorre } from "@/lib/consultas";
import { dataBR, ehDataISO, maiuscula, numeroLivre } from "@/lib/formato";
import { useAvisar } from "./avisos";
import { Aviso, Botao, Entrada, Selecao, cx, mensagem } from "./ui";

const OCULTOS = new Set(["alertas_sigbm"]);

function rotuloLivre(campo: string): string {
  return maiuscula(campo.replace(/_/g, " "));
}

/** O valor como gente lê: sim/não, número brasileiro, data, a opção pelo nome. */
export function valorDoCadastro(v: unknown, campo?: CampoCadastro): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "sim" : "não";
  if (typeof v === "number") return numeroLivre(v);
  if (typeof v === "string") {
    const op = campo?.opcoes.find((o) => o.valor === v);
    if (op) return op.rotulo;
    if (ehDataISO(v)) return dataBR(v);
    return String(v).replace(/_/g, " ");
  }
  if (Array.isArray(v)) return v.join("; ");
  return JSON.stringify(v);
}

type Rascunho = Record<string, string>;

function paraTexto(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "boolean") return v ? "sim" : "não";
  return String(v);
}

function deTexto(texto: string, tipo: string): unknown {
  if (tipo === "booleano") return texto === "sim";
  if (tipo === "numero") return Number(texto.replace(",", "."));
  return texto.trim();
}

/**
 * O cadastro do ativo, editável: o que decide se uma obrigação vale. O que falta (dado faltando) vem
 * primeiro e marcado; o resto pode ser corrigido. Só o que mudou vai para a API.
 */
export function EditorCadastro({ ativo, faltando }: { ativo: Ativo; faltando: string[] }) {
  const campos = useCamposCadastro();
  const avisar = useAvisar();
  const invalidar = useInvalidarTorre();
  const base = useId();
  const [rascunho, setRascunho] = useState<Rascunho>({});

  const linhas = useMemo(() => {
    const catalogo = (campos.data ?? []).filter((c) => c.tipos_ativo.includes(ativo.tipo));
    const doCatalogo = new Set(catalogo.map((c) => c.campo));
    const extras: CampoCadastro[] = Object.keys(ativo.atributos)
      .filter((k) => !doCatalogo.has(k) && !OCULTOS.has(k))
      .map((k) => ({ campo: k, rotulo: rotuloLivre(k), pergunta: rotuloLivre(k), tipo: "texto", opcoes: [], tipos_ativo: [ativo.tipo] }));
    // também o que falta e não está no catálogo do tipo
    for (const f of faltando) {
      if (!doCatalogo.has(f) && !extras.some((e) => e.campo === f)) {
        const c = campos.data?.find((x) => x.campo === f);
        extras.push(c ?? { campo: f, rotulo: rotuloLivre(f), pergunta: rotuloLivre(f), tipo: "texto", opcoes: [], tipos_ativo: [ativo.tipo] });
      }
    }
    const todos = [...catalogo, ...extras];
    const falta = new Set(faltando);
    return todos
      .filter((c) => falta.has(c.campo) || c.campo in ativo.atributos)
      .sort((a, b) => Number(falta.has(b.campo)) - Number(falta.has(a.campo)));
  }, [campos.data, ativo, faltando]);

  const mudou = Object.entries(rascunho).filter(([k, v]) => v !== "" && v !== paraTexto(ativo.atributos[k]));
  const salvar = useMutation({
    mutationFn: () => {
      const novos: Record<string, unknown> = {};
      for (const [k, v] of mudou) novos[k] = deTexto(v, linhas.find((c) => c.campo === k)?.tipo ?? "texto");
      return dados(api.PATCH("/api/v1/ativos/{ativo_id}/atributos", { params: { path: { ativo_id: ativo.id } }, body: { atributos: novos } }));
    },
    onSuccess: () => {
      avisar(`Cadastro de ${ativo.codigo} atualizado: a torre recalculou o que vale.`);
      setRascunho({});
      invalidar();
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });

  if (campos.isLoading) return null;
  const falta = new Set(faltando);

  return (
    <form onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }} className="space-y-3" data-testid="cadastro">
      {faltando.length > 0 && (
        <Aviso tipo="atencao">
          Falta no cadastro ({faltando.length}): sem esse dado não dá para dizer se algumas obrigações valem. Nada é presumido.
        </Aviso>
      )}
      <div className="overflow-hidden rounded-lg border border-borda">
        <table className="w-full text-sm">
          <thead className="bg-fundo-2 text-left text-xs text-texto-2">
            <tr><th className="px-3 py-2 font-medium">Dado</th><th className="px-3 py-2 font-medium">Valor</th></tr>
          </thead>
          <tbody className="divide-y divide-borda">
            {linhas.map((c) => {
              const id = `${base}-${c.campo}`;
              const atual = ativo.atributos[c.campo];
              const valor = rascunho[c.campo] ?? paraTexto(atual);
              const set = (v: string) => setRascunho((r) => ({ ...r, [c.campo]: v }));
              return (
                <tr key={c.campo} className={cx(falta.has(c.campo) && "bg-faltando-fundo")}>
                  <td className="px-3 py-2 align-top">
                    <label htmlFor={id} className="font-medium">{c.rotulo}</label>
                    {falta.has(c.campo) && <p className="text-xs text-faltando">{maiuscula(c.pergunta)}</p>}
                  </td>
                  <td className="w-[45%] px-3 py-1.5">
                    {c.tipo === "booleano" ? (
                      <Selecao id={id} value={valor} onChange={(e) => set(e.target.value)} className="h-8">
                        <option value="">não sei</option>
                        <option value="sim">sim</option>
                        <option value="não">não</option>
                      </Selecao>
                    ) : c.tipo === "opcoes" ? (
                      <Selecao id={id} value={valor} onChange={(e) => set(e.target.value)} className="h-8">
                        <option value="">—</option>
                        {c.opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
                      </Selecao>
                    ) : (
                      <Entrada id={id} className="h-8" value={valor} onChange={(e) => set(e.target.value)}
                        type={c.tipo === "numero" ? "number" : c.tipo === "data" ? "date" : "text"} step="any" />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {(ativo.atributos.alertas_sigbm as string[] | undefined)?.map((a) => <Aviso key={a} tipo="atencao">SIGBM: {a}</Aviso>)}
      <div className="flex items-center gap-3">
        <Botao type="submit" variante="primario" icone={<Save className="size-4" />} disabled={!mudou.length} carregando={salvar.isPending}>
          Salvar no cadastro
        </Botao>
        {mudou.length > 0 && <span className="text-xs text-texto-2">{mudou.length} {mudou.length === 1 ? "dado mudou" : "dados mudaram"}</span>}
      </div>
    </form>
  );
}
