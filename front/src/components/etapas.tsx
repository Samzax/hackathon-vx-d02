"use client";

// Uma etapa da instanciação, do jeito que a API devolve: título, estado tirado dos dados, os números
// da etapa, quem mexeu por último e, quando ainda não está pronta, o que falta. A tela não decide
// estado nem escreve o que falta: só dá forma ao que veio.
import type { Esquemas } from "@/lib/api";
import { emBrasilia, plural } from "@/lib/formato";
import { Cartao, Etiqueta, cx } from "./ui";

export type Etapa = Esquemas["Etapa"];

type Tom = "ok" | "marca" | "neutro";
type Forma = { rotulo: string; tom: Tom; borda: string };

/** Os três estados do contrato, com a cor da torre: pronta verde, em andamento na marca, pendente cinza. */
const ESTADOS: Record<string, Forma> = {
  pronta: { rotulo: "pronta", tom: "ok", borda: "border-l-emdia" },
  em_andamento: { rotulo: "em andamento", tom: "marca", borda: "border-l-marca" },
  pendente: { rotulo: "pendente", tom: "neutro", borda: "border-l-borda-forte" },
};

function forma(estado: string): Forma {
  return ESTADOS[estado] ?? { rotulo: estado.replaceAll("_", " "), tom: "neutro", borda: "border-l-borda-forte" };
}

/** Os números de cada etapa em português; chave nova que a API mandar aparece com o nome dela. */
const NUMEROS: Record<string, (n: number) => string> = {
  ufs: (n) => plural(n, "UF", "UFs"),
  ativos: (n) => plural(n, "ativo", "ativos"),
  unidades: (n) => plural(n, "unidade", "unidades"),
  faltando: (n) => plural(n, "dado faltando", "dados faltando"),
  ativos_com_falta: (n) => `${plural(n, "ativo", "ativos")} com dado faltando`,
  licencas: (n) => plural(n, "licença", "licenças"),
  propostas: (n) => plural(n, "condicionante proposta", "condicionantes propostas"),
  aprovadas: (n) => plural(n, "condicionante aprovada", "condicionantes aprovadas"),
  rejeitadas: (n) => plural(n, "condicionante rejeitada", "condicionantes rejeitadas"),
  responsaveis: (n) => plural(n, "responsável técnico", "responsáveis técnicos"),
  sem_responsavel: (n) => `${plural(n, "unidade ou ativo", "unidades ou ativos")} sem responsável`,
  contas: (n) => plural(n, "conta ativa", "contas ativas"),
  provisorias: (n) => plural(n, "senha provisória", "senhas provisórias"),
  ti: (n) => plural(n, "conta de TI", "contas de TI"),
};

function numeroDaEtapa(chave: string, n: number): string {
  const texto = NUMEROS[chave];
  return texto ? texto(n) : `${plural(n, chave.replaceAll("_", " "), chave.replaceAll("_", " "))}`;
}

function ultimoToque(e: Etapa): string {
  const quando = e.em ? emBrasilia(e.em) : "";
  if (e.por && quando) return `Mexeu por último: ${e.por}, em ${quando}.`;
  if (e.por) return `Mexeu por último: ${e.por}.`;
  if (quando) return `Mexeu por último em ${quando}.`;
  return "Ninguém mexeu nesta etapa ainda.";
}

export function EtapaDaInstanciacao({ etapa, indice }: { etapa: Etapa; indice: number }) {
  const f = forma(etapa.estado);
  const numeros = Object.entries(etapa.numeros)
    .filter(([, n]) => n > 0)
    .map(([chave, n]) => numeroDaEtapa(chave, n));

  return (
    <li data-testid={`etapa-${etapa.etapa}`} data-estado={etapa.estado}>
      <Cartao className={cx("border-l-4 p-4", f.borda)}>
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
          <div className="flex min-w-0 gap-2.5">
            <span className="num pt-0.5 text-xs font-semibold text-texto-3" aria-hidden>
              {String(indice).padStart(2, "0")}
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">{etapa.titulo}</h3>
              {numeros.length > 0 && (
                <p className="num mt-0.5 text-[13px] text-texto-2">{numeros.join(" · ")}</p>
              )}
            </div>
          </div>
          <Etiqueta tom={f.tom}>{f.rotulo}</Etiqueta>
        </div>

        {etapa.falta && (
          <p className="mt-2 text-[13px]">
            <span className="font-semibold">Falta:</span> {etapa.falta}
          </p>
        )}

        <p className="mt-1.5 text-xs text-texto-3">{ultimoToque(etapa)}</p>
      </Cartao>
    </li>
  );
}
