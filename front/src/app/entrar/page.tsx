"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/moldura";
import { Aviso, Botao, CampoEntrada, Cartao, mensagem } from "@/components/ui";
import { api, dados, type Esquemas } from "@/lib/api";

export default function Entrar() {
  const router = useRouter();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");

  const entrou = (eu: Esquemas["Eu"]) => {
    qc.clear();
    qc.setQueryData(["eu"], eu);
    router.replace(eu.papel_efetivo === "admin" ? "/usuarios/" : "/caixa/");
  };
  const demo = useMutation({ mutationFn: () => dados(api.POST("/api/v1/auth/demo")), onSuccess: entrou });
  const login = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/auth/login", { body: { email, senha } })),
    onSuccess: entrou,
  });
  const erro = demo.error ?? login.error;

  return (
    <main className="flex min-h-dvh items-center justify-center bg-fundo-2 px-4 py-10">
      <div className="w-full max-w-[400px]">
        <div className="mb-6 flex justify-center">
          <Logo className="h-9 w-auto" />
        </div>
        <Cartao className="px-6 py-7">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-texto-3">Torre de controle regulatória</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Entrar</h1>

          <Botao variante="primario" className="mt-5 w-full" icone={<Play className="size-4" />} carregando={demo.isPending}
            onClick={() => demo.mutate()}>
            Entrar na demo
          </Botao>
          <p className="mt-2 text-xs text-texto-2">
            Conta de teste da Mineradora Serra Azul (fictícia), sem senha: troque de visão (Diretoria, cada gestor, TI, curadoria)
            pelo menu.
          </p>

          <div className="my-6 flex items-center gap-3 text-xs text-texto-3">
            <span className="h-px flex-1 bg-borda" />ou com a sua conta<span className="h-px flex-1 bg-borda" />
          </div>

          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); login.mutate(); }}>
            <CampoEntrada rotulo="E-mail" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            <CampoEntrada rotulo="Senha" type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
            <Botao type="submit" className="w-full" carregando={login.isPending}>Entrar</Botao>
          </form>
          {erro && <Aviso tipo="erro" className="mt-4">{mensagem(erro)}.</Aviso>}
          <p className="mt-5 text-xs text-texto-3">Sem conta? Peça à TI da sua empresa: é ela que cria os acessos.</p>
        </Cartao>
      </div>
    </main>
  );
}
