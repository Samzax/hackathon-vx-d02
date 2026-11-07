"use client";

// A sessão e o que a moldura escolhe (empresa, "hoje", visão), para todas as telas.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, dados, ErroApi, type Esquemas } from "./api";

export type Eu = Esquemas["Eu"];
export type Empresa = Esquemas["Empresa"];

/** As viagens no tempo da demo. "Demo" é o hoje da torre (vem da API). */
export const RES_220 = "2027-08-02"; // Res. ANM 220/2025 substitui a Res. 95/2022
export const ZAS = "2029-12-27"; // dia seguinte ao prazo da ZAS (ANM e NR-22)

export type Torre = {
  eu: Eu;
  empresas: Empresa[];
  empresa: Empresa | null;
  setEmpresaId: (id: number) => void;
  hoje: string;
  hojeDemo: string;
  setHoje: (iso: string) => void;
  /** início da chave de toda consulta: muda a visão, a empresa ou o dia, a tela recarrega */
  chave: readonly unknown[];
  ti: boolean;
  veTudo: boolean;
  diretoria: boolean;
  plataforma: boolean;
  /** nos dados operacionais da empresa a sessão só lê (a plataforma): a tela esconde entrega, comentário, cadastro */
  soLeitura: boolean;
  trocarVisao: (visao: string) => Promise<void>;
  sair: () => Promise<void>;
};

const Contexto = createContext<Torre | null>(null);

function ler(chave: string): string | null {
  try {
    return localStorage.getItem(chave);
  } catch {
    return null;
  }
}

function gravar(chave: string, valor: string | null) {
  try {
    if (valor === null) localStorage.removeItem(chave);
    else localStorage.setItem(chave, valor);
  } catch {
    /* navegador sem armazenamento: só não lembra */
  }
}

export function useEu() {
  return useQuery({ queryKey: ["eu"], queryFn: () => dados(api.GET("/api/v1/auth/me")), retry: false, staleTime: 60_000 });
}

export function TorreProvider({ children, carregando, erro }:
  { children: React.ReactNode; carregando: React.ReactNode; erro: (e: unknown) => React.ReactNode }) {
  const router = useRouter();
  const qc = useQueryClient();
  const eu = useEu();
  const ti = eu.data?.papel_efetivo === "admin";
  const empresas = useQuery({
    queryKey: ["empresas", eu.data?.visao],
    queryFn: () => dados(api.GET("/api/v1/empresas")),
    enabled: !!eu.data && !ti,
  });
  const [empresaEscolhida, setEmpresaEscolhida] = useState<number | null>(() => Number(ler("mitra_empresa")) || null);
  const [hojeEscolhido, setHojeEscolhido] = useState<string | null>(() => ler("mitra_hoje"));

  useEffect(() => {
    if (eu.error instanceof ErroApi && eu.error.status === 401) router.replace("/entrar/");
  }, [eu.error, router]);

  const lista = useMemo(() => empresas.data ?? [], [empresas.data]);
  const empresa = lista.find((e) => e.id === empresaEscolhida) ?? lista[0] ?? null;
  const hojeDemo = eu.data?.hoje ?? "";
  const hoje = hojeEscolhido ?? hojeDemo;

  const setEmpresaId = useCallback((id: number) => {
    setEmpresaEscolhida(id);
    gravar("mitra_empresa", String(id));
  }, []);
  const setHoje = useCallback((iso: string) => {
    const v = iso && iso !== hojeDemo ? iso : null;
    setHojeEscolhido(v);
    gravar("mitra_hoje", v);
  }, [hojeDemo]);

  const trocarVisao = useCallback(async (visao: string) => {
    const novo = await dados(api.PUT("/api/v1/auth/visao", { body: { visao } }));
    qc.setQueryData(["eu"], novo);
    await qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "eu" });
  }, [qc]);

  const sair = useCallback(async () => {
    await api.POST("/api/v1/auth/logout").catch(() => undefined);
    qc.clear();
    router.replace("/entrar/");
  }, [qc, router]);

  const valor = useMemo<Torre | null>(() => {
    if (!eu.data) return null;
    const d = eu.data;
    return {
      eu: d, empresas: lista, empresa, setEmpresaId, hoje, hojeDemo, setHoje,
      chave: ["torre", d.visao, empresa?.id ?? null, hoje] as const,
      ti: d.papel_efetivo === "admin",
      veTudo: d.papel_efetivo === "diretoria" || d.papel_efetivo === "regulatorio",
      diretoria: d.papel_efetivo === "diretoria",
      plataforma: d.plataforma,
      soLeitura: d.so_leitura,
      trocarVisao, sair,
    };
  }, [eu.data, lista, empresa, setEmpresaId, hoje, hojeDemo, setHoje, trocarVisao, sair]);

  if (eu.error && !(eu.error instanceof ErroApi && eu.error.status === 401)) return <>{erro(eu.error)}</>;
  if (empresas.error) return <>{erro(empresas.error)}</>;
  if (!valor || (!valor.ti && !empresas.data)) return <>{carregando}</>;
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useTorre(): Torre {
  const t = useContext(Contexto);
  if (!t) throw new Error("useTorre fora da moldura");
  return t;
}

/** A empresa escolhida (as telas da torre só aparecem quando há uma). */
export function useEmpresa(): Empresa {
  const { empresa } = useTorre();
  if (!empresa) throw new Error("sem empresa");
  return empresa;
}
