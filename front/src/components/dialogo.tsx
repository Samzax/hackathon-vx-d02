"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { cx } from "./ui";

/** Diálogo modal nativo (<dialog>): foco preso, Esc fecha, clique fora fecha. */
export function Dialogo({ aberto, onFechar, titulo, children, largura = "md", rodape }:
  { aberto: boolean; onFechar: () => void; titulo: React.ReactNode; children: React.ReactNode; largura?: "md" | "lg"; rodape?: React.ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (aberto && !d.open) d.showModal();
    if (!aberto && d.open) d.close();
  }, [aberto]);
  return (
    <dialog
      ref={ref}
      onClose={onFechar}
      onCancel={(e) => { e.preventDefault(); onFechar(); }}
      onClick={(e) => { if (e.target === ref.current) onFechar(); }}
      aria-labelledby="dialogo-titulo"
      className={cx(
        "m-auto max-h-[90dvh] w-[calc(100%-2rem)] overflow-visible rounded-xl border border-borda bg-fundo p-0 text-texto shadow-2xl",
        largura === "lg" ? "max-w-3xl" : "max-w-lg",
      )}
    >
      {aberto && (
        <div className="flex max-h-[90dvh] flex-col">
          <div className="flex items-start gap-3 border-b border-borda px-5 py-4">
            <h2 id="dialogo-titulo" className="min-w-0 flex-1 text-base font-semibold">{titulo}</h2>
            <button type="button" onClick={onFechar} aria-label="Fechar" className="rounded p-1 text-texto-3 hover:bg-fundo-2 hover:text-texto">
              <X className="size-4" />
            </button>
          </div>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
          {rodape && <div className="flex flex-wrap justify-end gap-2 border-t border-borda px-5 py-3">{rodape}</div>}
        </div>
      )}
    </dialog>
  );
}
