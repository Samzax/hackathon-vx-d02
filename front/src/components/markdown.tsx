import { type Bloco, type Trecho, lerMarkdown } from "@/lib/markdown";
import { cx } from "./ui";

function Linha({ trechos }: { trechos: Trecho[] }) {
  return (
    <>
      {trechos.map((t, i) =>
        t.tipo === "negrito" ? <strong key={i}>{t.texto}</strong>
          : t.tipo === "italico" ? <em key={i}>{t.texto}</em>
            : t.tipo === "codigo" ? <code key={i} className="rounded bg-fundo-3 px-1 text-[0.9em]">{t.texto}</code>
              : <span key={i}>{t.texto}</span>,
      )}
    </>
  );
}

const TITULO = ["text-lg font-semibold", "mt-4 text-base font-semibold", "mt-3 text-sm font-semibold"];

/** O boletim e o plano de transição, como a API escreveu. `semTitulo` tira o título grande do topo. */
export function Markdown({ texto, semTitulo, className }: { texto: string; semTitulo?: boolean; className?: string }) {
  let blocos: Bloco[] = lerMarkdown(texto);
  if (semTitulo && blocos[0]?.tipo === "titulo" && blocos[0].nivel === 1) blocos = blocos.slice(1);
  return (
    <div className={cx("space-y-2 text-sm leading-relaxed", className)}>
      {blocos.map((b, i) => {
        if (b.tipo === "titulo") {
          const nivel = Math.min(b.nivel, 3) - 1;
          return <p key={i} role="heading" aria-level={b.nivel + 1} className={TITULO[nivel]}><Linha trechos={b.trechos} /></p>;
        }
        if (b.tipo === "lista") {
          return (
            <ul key={i} className="space-y-1">
              {b.itens.map((it, j) => (
                <li key={j} className="flex gap-2" style={{ paddingLeft: `${it.nivel * 1.25}rem` }}>
                  <span className="text-texto-3" aria-hidden>{it.nivel ? "–" : "•"}</span>
                  <span><Linha trechos={it.trechos} /></span>
                </li>
              ))}
            </ul>
          );
        }
        return <p key={i}><Linha trechos={b.trechos} /></p>;
      })}
    </div>
  );
}
