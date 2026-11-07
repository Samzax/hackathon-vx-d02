"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Carregando } from "@/components/ui";
import { ErroApi } from "@/lib/api";
import { useEu } from "@/lib/torre";

/** Raiz: quem já entrou vai para a tela inicial do papel; quem não entrou, para a tela de entrada. */
export default function Inicio() {
  const router = useRouter();
  const eu = useEu();
  useEffect(() => {
    if (eu.data) router.replace(eu.data.papel_efetivo === "admin" ? "/usuarios/" : "/caixa/");
    else if (eu.error) router.replace(eu.error instanceof ErroApi && eu.error.status !== 401 ? "/caixa/" : "/entrar/");
  }, [eu.data, eu.error, router]);
  return <div className="mx-auto max-w-3xl p-8"><Carregando /></div>;
}
