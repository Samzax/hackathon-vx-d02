"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Save, UserPlus } from "lucide-react";
import { useState } from "react";
import { useAvisar } from "@/components/avisos";
import {
  Abas, Aviso, Botao, Carregando, Cartao, Campo, CampoEntrada, CampoSelecao, Entrada, ErroCarga, Etiqueta, Titulo, mensagem,
} from "@/components/ui";
import { api, dados, type Esquemas } from "@/lib/api";
import { emBrasilia } from "@/lib/formato";
import { useTorre } from "@/lib/torre";

type Conta = Esquemas["ContaVista"];
type Contas = Esquemas["Contas"];
const GESTOR = "gestor";
const SENHA_MINIMA = 8;

function useContas() {
  const t = useTorre();
  return useQuery({ queryKey: ["contas", t.eu.visao], queryFn: () => dados(api.GET("/api/v1/usuarios")) });
}

function CampoArea({ valor, onMudar, areas, desligado }: { valor: string; onMudar: (v: string) => void; areas: string[]; desligado?: boolean }) {
  return (
    <Campo rotulo="Área (só para gestor)" dica="Escolha ou digite uma área nova.">
      <Entrada list="areas-contas" value={valor} onChange={(e) => onMudar(e.target.value)} disabled={desligado} aria-label="Área (só para gestor)"
        placeholder={desligado ? "só para gestor" : "ex.: Gerência de Geotecnia"} />
      <datalist id="areas-contas">{areas.map((a) => <option key={a} value={a} />)}</datalist>
    </Campo>
  );
}

function NovaConta({ c }: { c: Contas }) {
  const t = useTorre();
  const qc = useQueryClient();
  const avisar = useAvisar();
  const vazio = { nome: "", email: "", papel: GESTOR, area: "", senha: "", empresa: c.empresas[0] ?? "" };
  const [f, setF] = useState(vazio);
  const criar = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/usuarios", {
      body: {
        nome: f.nome.trim(), email: f.email.trim(), papel: f.papel, area: f.papel === GESTOR ? f.area.trim() || null : null,
        senha: f.senha || null, empresa: t.plataforma ? f.empresa || null : null,
      },
    })),
    onSuccess: () => { avisar(`Conta de ${f.nome.trim()} criada`); setF(vazio); void qc.invalidateQueries({ queryKey: ["contas"] }); },
  });
  return (
    <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); criar.mutate(); }}>
      <CampoEntrada rotulo="Nome" required value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />
      <CampoEntrada rotulo="E-mail" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
      <CampoSelecao rotulo="Papel" value={f.papel} onChange={(e) => setF({ ...f, papel: e.target.value })}>
        {Object.entries(c.papeis).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </CampoSelecao>
      <CampoArea valor={f.area} onMudar={(area) => setF({ ...f, area })} areas={c.areas} desligado={f.papel !== GESTOR} />
      <CampoEntrada rotulo="Senha inicial" type="password" autoComplete="new-password" value={f.senha} minLength={SENHA_MINIMA}
        onChange={(e) => setF({ ...f, senha: e.target.value })} dica={`Pelo menos ${SENHA_MINIMA} caracteres. Vazio: a pessoa não entra até a TI definir uma.`} />
      {t.plataforma && (
        <CampoSelecao rotulo="Empresa" value={f.empresa} onChange={(e) => setF({ ...f, empresa: e.target.value })}
          dica="Vazio cria uma conta da plataforma (equipe da Mitra).">
          <option value="">— plataforma Mitra</option>
          {c.empresas.map((e) => <option key={e} value={e}>{e}</option>)}
        </CampoSelecao>
      )}
      {criar.error && <Aviso tipo="erro" className="sm:col-span-2">{mensagem(criar.error)}.</Aviso>}
      <div className="sm:col-span-2">
        <Botao type="submit" variante="primario" icone={<UserPlus className="size-4" />} carregando={criar.isPending}>Criar conta</Botao>
      </div>
    </form>
  );
}

function EditarConta({ c }: { c: Contas }) {
  const [id, setId] = useState<number>(c.contas[0]?.id ?? 0);
  const u = c.contas.find((x) => x.id === id) ?? c.contas[0];
  if (!u) return <p className="text-sm text-texto-2">Nenhuma conta.</p>;
  return (
    <div className="space-y-4">
      <CampoSelecao rotulo="Conta" value={u.id} onChange={(e) => setId(Number(e.target.value))} className="max-w-xl">
        {c.contas.map((x) => <option key={x.id} value={x.id}>{x.nome} · {x.email}</option>)}
      </CampoSelecao>
      <FormEdicao key={`${u.id}-${u.papel}-${u.area}-${u.ativa}`} u={u} c={c} />
    </div>
  );
}

function FormEdicao({ u, c }: { u: Conta; c: Contas }) {
  const qc = useQueryClient();
  const avisar = useAvisar();
  const [f, setF] = useState({ nome: u.nome, papel: u.papel, area: u.area ?? "", ativa: u.ativa });
  const [senha, setSenha] = useState("");
  const salvar = useMutation({
    mutationFn: () => dados(api.PATCH("/api/v1/usuarios/{usuario_id}", {
      params: { path: { usuario_id: u.id } },
      body: { nome: f.nome.trim(), papel: f.papel, area: f.papel === GESTOR ? f.area.trim() : "", ativa: f.ativa },
    })),
    onSuccess: () => { avisar(`Conta de ${f.nome.trim()} salva`); void qc.invalidateQueries({ queryKey: ["contas"] }); },
  });
  const trocarSenha = useMutation({
    mutationFn: () => dados(api.PUT("/api/v1/usuarios/{usuario_id}/senha", { params: { path: { usuario_id: u.id } }, body: { senha } })),
    onSuccess: () => { avisar(`Senha de ${u.nome} trocada; as sessões abertas dela foram encerradas.`); setSenha(""); },
  });
  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <CampoEntrada rotulo="Nome" required value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />
        <CampoSelecao rotulo="Papel" value={f.papel} onChange={(e) => setF({ ...f, papel: e.target.value })}>
          {Object.entries(c.papeis).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </CampoSelecao>
        <CampoArea valor={f.area} onMudar={(area) => setF({ ...f, area })} areas={c.areas} desligado={f.papel !== GESTOR} />
        <label className="flex items-center gap-2 self-center text-sm">
          <input type="checkbox" checked={f.ativa} onChange={(e) => setF({ ...f, ativa: e.target.checked })} className="size-4 accent-[var(--marca)]" />
          Conta ativa
        </label>
        {salvar.error && <Aviso tipo="erro" className="sm:col-span-2">{mensagem(salvar.error)}.</Aviso>}
        <div className="sm:col-span-2">
          <Botao type="submit" variante="primario" icone={<Save className="size-4" />} carregando={salvar.isPending}>Salvar</Botao>
        </div>
      </form>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); trocarSenha.mutate(); }}>
        <CampoEntrada rotulo="Nova senha" type="password" autoComplete="new-password" minLength={SENHA_MINIMA} value={senha}
          onChange={(e) => setSenha(e.target.value)} dica={`Pelo menos ${SENHA_MINIMA} caracteres.`} />
        {trocarSenha.error && <Aviso tipo="erro">{mensagem(trocarSenha.error)}.</Aviso>}
        <Botao type="submit" icone={<KeyRound className="size-4" />} disabled={senha.length < SENHA_MINIMA} carregando={trocarSenha.isPending}>Trocar senha</Botao>
      </form>
    </div>
  );
}

export default function Usuarios() {
  const contas = useContas();
  const [aba, setAba] = useState<"nova" | "editar">("nova");
  if (contas.isLoading) return <Carregando linhas={6} />;
  if (contas.error) return <ErroCarga erro={contas.error} onTentar={() => contas.refetch()} />;
  const c = contas.data!;
  return (
    <>
      <Titulo titulo="Usuários e acessos">
        O papel define o que cada pessoa vê, e a Diretoria decide a área de cada ativo. A TI administra contas e não vê
        dado regulatório.
      </Titulo>
      <div className="overflow-x-auto rounded-lg border border-borda">
        <table className="w-full min-w-[860px] text-sm" data-testid="contas">
          <thead className="bg-fundo-2 text-left text-xs text-texto-2">
            <tr>{["Nome", "E-mail", "Papel", "Área", "Empresa", "Situação", "Último acesso"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-borda">
            {c.contas.map((u) => (
              <tr key={u.id}>
                <td className="px-3 py-2 font-medium">{u.nome}{u.teste && <Etiqueta tom="marca" className="ml-1.5">teste</Etiqueta>}</td>
                <td className="px-3 py-2 text-texto-2">{u.email}</td>
                <td className="px-3 py-2">{c.papeis[u.papel] ?? u.papel}</td>
                <td className="px-3 py-2 text-texto-2">{u.area ?? "—"}</td>
                <td className="px-3 py-2 text-texto-2">{u.plataforma ? "plataforma Mitra" : u.empresa ?? "—"}</td>
                <td className="px-3 py-2">{u.ativa ? <Etiqueta tom="ok">ativa</Etiqueta> : <Etiqueta tom="neutro">desativada</Etiqueta>}{!u.tem_senha && <span className="ml-1.5 text-xs text-texto-3">sem senha</span>}</td>
                <td className="num px-3 py-2 text-texto-2">{u.ultimo_acesso ? emBrasilia(u.ultimo_acesso) : "nunca"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Cartao className="mt-6 p-4 sm:p-5">
        <Abas rotulo="Contas" ativa={aba} onTrocar={setAba} abas={[{ id: "nova", rotulo: "Nova conta" }, { id: "editar", rotulo: "Editar conta" }]} />
        <div className="pt-4">{aba === "nova" ? <NovaConta c={c} /> : <EditarConta c={c} />}</div>
      </Cartao>
    </>
  );
}
