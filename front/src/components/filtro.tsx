"use client";

import { Check, ChevronDown, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { cx } from "./ui";

export type Opcao = { valor: string; rotulo: string };

/** Filtro de várias escolhas: um botão que abre a lista com caixas de marcar. Vazio = todos. */
export function FiltroMulti({ rotulo, opcoes, valor, onMudar, todos = "todos" }:
  { rotulo: string; opcoes: Opcao[]; valor: string[]; onMudar: (v: string[]) => void; todos?: string }) {
  const [aberto, setAberto] = useState(false);
  const caixa = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => { if (!caixa.current?.contains(e.target as Node)) setAberto(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setAberto(false); };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fora); document.removeEventListener("keydown", esc); };
  }, [aberto]);

  const escolhidos = opcoes.filter((o) => valor.includes(o.valor));
  const resumo = !escolhidos.length ? todos : escolhidos.length <= 3 ? escolhidos.map((o) => o.rotulo).join(", ") : `${escolhidos.length} escolhidos`;
  const alternar = (v: string) => onMudar(valor.includes(v) ? valor.filter((x) => x !== v) : [...valor, v]);

  return (
    <div ref={caixa} className="relative flex flex-col gap-1">
      <span id={`${id}-r`} className="text-[13px] font-medium text-texto-2">{rotulo}</span>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={aberto}
        aria-labelledby={`${id}-r ${id}-v`}
        onClick={() => setAberto((a) => !a)}
        className={cx("flex h-9 w-full items-center gap-2 rounded-md border bg-fundo px-2.5 text-left text-sm",
          escolhidos.length ? "border-marca" : "border-borda-forte")}
      >
        <span id={`${id}-v`} className={cx("min-w-0 flex-1 truncate", !escolhidos.length && "text-texto-3")}>{resumo}</span>
        {escolhidos.length > 0 && (
          <span role="button" tabIndex={0} aria-label={`Limpar ${rotulo}`}
            onClick={(e) => { e.stopPropagation(); onMudar([]); }}
            onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); onMudar([]); } }}
            className="rounded p-0.5 text-texto-3 hover:bg-fundo-2 hover:text-texto">
            <X className="size-3.5" />
          </span>
        )}
        <ChevronDown className="size-4 shrink-0 text-texto-3" aria-hidden />
      </button>
      {aberto && (
        <ul role="listbox" aria-multiselectable="true" aria-label={rotulo}
          className="absolute top-full z-30 mt-1 max-h-72 w-full min-w-56 overflow-y-auto rounded-md border border-borda bg-fundo py-1 shadow-lg">
          {opcoes.map((o) => {
            const sim = valor.includes(o.valor);
            return (
              <li key={o.valor} role="option" aria-selected={sim} tabIndex={0}
                onClick={() => alternar(o.valor)}
                onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); alternar(o.valor); } }}
                className="flex cursor-pointer items-center gap-2 px-2.5 py-1.5 text-sm hover:bg-fundo-2">
                <span className={cx("flex size-4 shrink-0 items-center justify-center rounded border",
                  sim ? "border-marca bg-marca text-sobre-marca" : "border-borda-forte")}>
                  {sim && <Check className="size-3" />}
                </span>
                {o.rotulo}
              </li>
            );
          })}
          {!opcoes.length && <li className="px-2.5 py-1.5 text-sm text-texto-3">nada para escolher</li>}
        </ul>
      )}
    </div>
  );
}
