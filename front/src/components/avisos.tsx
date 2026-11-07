"use client";

import { CheckCircle2, TriangleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";

type Aviso = { id: number; texto: string; tipo: "ok" | "erro" };
type Avisar = (texto: string, tipo?: Aviso["tipo"]) => void;

const Contexto = createContext<Avisar>(() => {});

/** Avisos curtos no canto da tela ("Entrega registrada: B3 · R95-01"). Somem sozinhos. */
export function Avisos({ children }: { children: React.ReactNode }) {
  const [lista, setLista] = useState<Aviso[]>([]);
  const avisar = useCallback<Avisar>((texto, tipo = "ok") => {
    const id = Date.now() + Math.random();
    setLista((l) => [...l, { id, texto, tipo }]);
    setTimeout(() => setLista((l) => l.filter((a) => a.id !== id)), tipo === "erro" ? 9000 : 5000);
  }, []);
  return (
    <Contexto.Provider value={avisar}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4 sm:items-end">
        {lista.map((a) => (
          <div
            key={a.id}
            role={a.tipo === "erro" ? "alert" : "status"}
            className="pointer-events-auto flex max-w-md items-start gap-2 rounded-lg border border-borda bg-fundo px-3.5 py-2.5 text-sm shadow-lg"
          >
            {a.tipo === "ok" ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emdia" aria-hidden />
            ) : (
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-atrasada" aria-hidden />
            )}
            <span className="flex-1">{a.texto}</span>
            <button
              type="button"
              onClick={() => setLista((l) => l.filter((x) => x.id !== a.id))}
              className="text-texto-3 hover:text-texto"
              aria-label="Fechar aviso"
            >
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </Contexto.Provider>
  );
}

export function useAvisar(): Avisar {
  return useContext(Contexto);
}
