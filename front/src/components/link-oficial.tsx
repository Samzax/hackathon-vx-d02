import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

/** Texto que abre a publicação oficial (norma, página do DOU) em nova aba; sem endereço, só o texto. */
export function LinkOficial({ href, children }: { href?: string | null; children: ReactNode }) {
  if (!href) return <>{children}</>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" title="Abrir texto oficial em nova aba"
      className="inline-flex items-center gap-1 underline decoration-borda-forte underline-offset-2 hover:text-marca hover:decoration-marca">
      {children}
      <ExternalLink className="size-3 shrink-0" aria-hidden />
      <span className="sr-only">(abre em nova aba)</span>
    </a>
  );
}
