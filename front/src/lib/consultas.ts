"use client";

// As consultas das telas. A chave começa pela visão, a empresa e o dia (useTorre().chave):
// trocar qualquer um deles recarrega o que depende dele, e uma escrita invalida a torre inteira.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, dados, enviarArquivo, type Esquemas } from "./api";
import { useTorre } from "./torre";

export type Linha = Esquemas["LinhaPainel"];
export type Painel = Esquemas["Painel"];
export type Ativo = Esquemas["Ativo"];
export type Ficha = Esquemas["Ficha"];
export type Mudanca = Esquemas["Mudanca"];
export type Leitura = Esquemas["ResultadoLeitura"];
export type CampoCadastro = Esquemas["CampoCadastro"];

function useBase() {
  const t = useTorre();
  return { t, id: t.empresa?.id ?? 0, hoje: t.hoje, chave: t.chave };
}

export function usePainel() {
  const { id, hoje, chave } = useBase();
  return useQuery({
    queryKey: [...chave, "painel"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/painel", { params: { path: { empresa_id: id }, query: { hoje } } })),
    enabled: !!id,
  });
}

export function useAtivos() {
  const { id, hoje, chave } = useBase();
  return useQuery({
    queryKey: [...chave, "ativos"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/ativos", { params: { path: { empresa_id: id }, query: { hoje } } })),
    enabled: !!id,
  });
}

export function useFicha(ativoId: number | null) {
  const { hoje, chave } = useBase();
  return useQuery({
    queryKey: [...chave, "ficha", ativoId],
    queryFn: () => dados(api.GET("/api/v1/ativos/{ativo_id}", { params: { path: { ativo_id: ativoId! }, query: { hoje } } })),
    enabled: ativoId !== null,
  });
}

export function useMudancas() {
  const { id, chave } = useBase();
  return useQuery({
    queryKey: [...chave, "mudancas"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/mudancas", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
}

export function useAreas() {
  const { id, chave } = useBase();
  return useQuery({
    queryKey: [...chave, "areas"],
    queryFn: () => dados(api.GET("/api/v1/empresas/{empresa_id}/areas", { params: { path: { empresa_id: id } } })),
    enabled: !!id,
  });
}

export function useCamposCadastro() {
  return useQuery({
    queryKey: ["campos-cadastro"],
    queryFn: () => dados(api.GET("/api/v1/cadastro/campos")),
    staleTime: Infinity,
  });
}

export function useRadar() {
  const { t, chave } = useBase();
  return useQuery({ queryKey: [chave[0], chave[1], "radar"], queryFn: () => dados(api.GET("/api/v1/radar")), enabled: !t.ti });
}

/** Depois de uma escrita, tudo o que é da torre pode ter mudado (contagens, ficha, calendário). */
export function useInvalidarTorre() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "torre" });
}

export type DadosEntrega = { ativo_id: number; codigo: string; dia?: string; obs?: string; arquivo?: File | null };

export function useEntregar() {
  const invalidar = useInvalidarTorre();
  return useMutation({
    mutationFn: async ({ arquivo, ...d }: DadosEntrega) => {
      let guardado: string | undefined;
      if (arquivo) {
        const c = await enviarArquivo<Esquemas["Comprovante"]>("/api/v1/comprovantes", { ativo_id: d.ativo_id }, arquivo);
        guardado = c.guardado_em;
      }
      return dados(api.POST("/api/v1/entregas", {
        body: { ativo_id: d.ativo_id, codigo: d.codigo, dia: d.dia || null, obs: d.obs || null, arquivo: guardado ?? null },
      }));
    },
    onSuccess: () => invalidar(),
  });
}
