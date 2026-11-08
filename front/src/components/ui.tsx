"use client";

import { ChevronDown, CircleAlert, Info, Loader2, OctagonAlert, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { forwardRef, useId, useRef, useState } from "react";
import { ErroApi } from "@/lib/api";
import { ROTULO, cor } from "@/lib/status";

export function cx(...c: (string | false | null | undefined)[]): string {
  return c.filter(Boolean).join(" ");
}

// ------------------------------------------------------------------ botões

type Variante = "primario" | "secundario" | "fantasma" | "perigo";
type Tamanho = "p" | "m";

const BASE_BOTAO =
  "inline-flex items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-50";
const VARIANTE: Record<Variante, string> = {
  primario: "bg-marca text-sobre-marca hover:bg-marca-forte",
  secundario: "border border-borda-forte bg-fundo text-texto hover:bg-fundo-2",
  fantasma: "text-marca hover:bg-marca-suave",
  perigo: "border border-atrasada/40 bg-fundo text-atrasada hover:bg-atrasada-fundo",
};
const TAMANHO: Record<Tamanho, string> = { p: "h-8 px-2.5 text-[13px]", m: "h-9 px-3.5 text-sm" };

export function classeBotao(variante: Variante = "secundario", tamanho: Tamanho = "m") {
  return cx(BASE_BOTAO, VARIANTE[variante], TAMANHO[tamanho]);
}

type PropsBotao = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: Variante;
  tamanho?: Tamanho;
  carregando?: boolean;
  icone?: React.ReactNode;
};

export const Botao = forwardRef<HTMLButtonElement, PropsBotao>(function Botao(
  { variante = "secundario", tamanho = "m", carregando, icone, className, children, disabled, type = "button", ...resto },
  ref,
) {
  return (
    <button ref={ref} type={type} disabled={disabled || carregando} className={cx(classeBotao(variante, tamanho), className)} {...resto}>
      {carregando ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icone}
      {children}
    </button>
  );
});

export function LinkBotao({ href, variante = "secundario", tamanho = "m", icone, className, children, ...resto }:
  React.ComponentProps<typeof Link> & { variante?: Variante; tamanho?: Tamanho; icone?: React.ReactNode }) {
  return (
    <Link href={href} className={cx(classeBotao(variante, tamanho), className)} {...resto}>
      {icone}
      {children}
    </Link>
  );
}

// ------------------------------------------------------------------ blocos

export function Cartao({ className, children, ...resto }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("rounded-lg border border-borda bg-fundo shadow-cartao", className)} {...resto}>
      {children}
    </div>
  );
}

function Dica({ descricao, tamanho }: { descricao: string; tamanho: "titulo" | "secao" | "numero" }) {
  const id = useId();
  const ancora = useRef<HTMLSpanElement>(null);
  const [aberta, setAberta] = useState(false);
  const [posicao, setPosicao] = useState({ esquerda: 0, largura: 256 });
  const tamanhos = {
    titulo: "h-3.5 w-3.5 text-[9px]",
    secao: "h-3 w-3 text-[8px]",
    numero: "h-3 w-3 text-[8px]",
  };
  const abrir = () => {
    const retangulo = ancora.current?.getBoundingClientRect();
    if (!retangulo) return;
    const margem = 16;
    const largura = Math.min(256, window.innerWidth - margem * 2);
    const esquerdaNaTela = Math.min(Math.max(margem, retangulo.left), window.innerWidth - largura - margem);
    setPosicao({ esquerda: esquerdaNaTela - retangulo.left, largura });
    setAberta(true);
  };
  return (
    <span ref={ancora} className="relative ml-1 inline-flex align-middle" onMouseEnter={abrir} onMouseLeave={() => setAberta(false)} onFocus={abrir} onBlur={() => setAberta(false)}>
      <span
        aria-describedby={id}
        aria-label="Ver dica"
        tabIndex={0}
        className={cx("inline-flex items-center justify-center rounded-full bg-borda-forte text-texto-2", tamanhos[tamanho])}
      >
        ?
      </span>
      {aberta && (
        <span
          id={id}
          role="tooltip"
          style={{ left: posicao.esquerda, width: posicao.largura }}
          className="pointer-events-none absolute top-full z-50 mt-2 rounded-md border border-borda bg-fundo px-3 py-2 text-left text-xs font-normal leading-5 text-texto shadow-cartao"
        >
          {descricao}
        </span>
      )}
    </span>
  );
}

/** Dica de cada tela, pelo título. Vale para o "?" do título e para o menu lateral. */
export const TITULOS_DICAS: Record<string, string> = {
  "Caixa de entrada": "Central de obrigações que precisam de entrega ou atenção imediata",
  "Ativos": "Instalações, equipamentos e estruturas monitoradas",
  "Entregas": "Histórico de todas as entregas e registros já realizados",
  "Assistente Mitra": "Faça perguntas e receba respostas sobre regulamentações e conformidade",
  "Auditoria": "Registro de todas as ações realizadas no sistema",
  "Usuários e acessos": "Gerencie usuários e permissões de acesso",
  "Nova empresa": "Cadastro de uma nova empresa cliente na plataforma",
  "Instanciação": "Configuração dos parâmetros e regras da sua empresa",
  "Licenças": "Licenças de operação e condicionantes de segurança",
  "Responsáveis e unidades": "Cadastro dos responsáveis técnicos e unidades operacionais",
  "Mudanças": "Mudanças normativas que afetam suas obrigações",
  "Radar": "Monitoramento das publicações no Diário Oficial da União",
  "Transição e linha do tempo": "Cronologia e prazos de transição entre normas",
  "Cobertura normativa": "Normas que se aplicam à sua empresa e ativos",
  "Normas candidatas": "Normas em análise para inclusão no monitoramento",
  "Mercado": "Informações sobre o mercado e regulamentações do setor",
  "Como funciona": "Explicação sobre o funcionamento da torre de controle regulatória",
};

export function Titulo({ titulo, acoes, children, dica }: { titulo: string; acoes?: React.ReactNode; children?: React.ReactNode; dica?: string }) {
  const Descricao = dica ?? TITULOS_DICAS[titulo];
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">
          {titulo}
          {Descricao && (
            <Dica descricao={Descricao} tamanho="titulo" />
          )}
        </h1>
        {children && <div className="mt-1 max-w-3xl text-sm text-texto-2">{children}</div>}
      </div>
      {acoes && <div className="flex flex-wrap gap-2">{acoes}</div>}
    </div>
  );
}

const SECOES_DICAS: Record<string, string> = {
  "Responsáveis técnicos": "Cadastro das pessoas responsáveis pela operação e segurança",
  "Unidades": "Operações da empresa e os ativos de cada uma",
  "Obrigações": "Lista de todas as obrigações regulatórias da empresa",
  "Pendentes": "Obrigações que ainda não foram entregues",
  "Entregues": "Obrigações que já foram entregues",
  "Histórico": "Registro de todas as ações e alterações",
  "Configurações": "Configurações do sistema e preferências",
  "Relatórios": "Relatórios gerados pelo sistema",
  "Documentos": "Documentos e arquivos relacionados",
  "Notificações": "Notificações e alertas importantes",
};

export function Secao({ titulo, descricao, acoes, children, className, id, dica }:
  { titulo: React.ReactNode; descricao?: React.ReactNode; acoes?: React.ReactNode; children: React.ReactNode; className?: string; id?: string; dica?: string }) {
  const Descricao = dica ?? (typeof titulo === "string" ? SECOES_DICAS[titulo] : undefined);
  return (
    <section className={cx("mt-8 first:mt-0", className)} id={id} aria-labelledby={id ? `${id}-titulo` : undefined}>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id={id ? `${id}-titulo` : undefined} className="text-base font-semibold">
            {titulo}
            {Descricao && (
              <Dica descricao={Descricao} tamanho="secao" />
            )}
          </h2>
          {descricao && <p className="mt-0.5 max-w-3xl text-[13px] text-texto-2">{descricao}</p>}
        </div>
        {acoes && <div className="flex flex-wrap gap-2">{acoes}</div>}
      </div>
      {children}
    </section>
  );
}

// ------------------------------------------------------------------ etiquetas

export function Selo({ status, texto, className }: { status: string; texto?: string; className?: string }) {
  const c = cor(status);
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold", c.fundo, c.texto, className)}>
      <span className={cx("size-1.5 rounded-full", c.ponto)} aria-hidden />
      {texto ?? ROTULO[status] ?? status}
    </span>
  );
}

type Tom = "neutro" | "marca" | "atencao" | "perigo" | "ok" | "proposta";
const TOM: Record<Tom, string> = {
  neutro: "bg-fundo-3 text-texto-2",
  marca: "bg-marca-suave text-marca",
  atencao: "bg-vence-fundo text-vence",
  perigo: "bg-atrasada-fundo text-atrasada",
  ok: "bg-emdia-fundo text-emdia",
  proposta: "bg-vence-fundo text-proposta",
};

export function Etiqueta({ tom = "neutro", children, className, title }: { tom?: Tom; children: React.ReactNode; className?: string; title?: string }) {
  return <span title={title} className={cx("inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold", TOM[tom], className)}>{children}</span>;
}

type TipoAviso = "info" | "atencao" | "erro" | "sucesso";
const AVISO: Record<TipoAviso, { classe: string; icone: React.ReactNode }> = {
  info: { classe: "border-gatilho/30 bg-gatilho-fundo", icone: <Info className="size-4 text-gatilho" aria-hidden /> },
  atencao: { classe: "border-vence-marca/50 bg-vence-fundo", icone: <TriangleAlert className="size-4 text-vence" aria-hidden /> },
  erro: { classe: "border-atrasada/40 bg-atrasada-fundo", icone: <OctagonAlert className="size-4 text-atrasada" aria-hidden /> },
  sucesso: { classe: "border-emdia/30 bg-emdia-fundo", icone: <CircleAlert className="size-4 text-emdia" aria-hidden /> },
};

export function Aviso({ tipo = "info", children, className, icone }: { tipo?: TipoAviso; children: React.ReactNode; className?: string; icone?: React.ReactNode }) {
  const a = AVISO[tipo];
  return (
    <div role={tipo === "erro" ? "alert" : undefined} className={cx("flex gap-2.5 rounded-md border px-3 py-2.5 text-sm", a.classe, className)}>
      <span className="mt-0.5 shrink-0">{icone ?? a.icone}</span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

// ------------------------------------------------------------------ estados de carga

export function Carregando({ linhas = 3, className }: { linhas?: number; className?: string }) {
  return (
    <div className={cx("space-y-2", className)} aria-busy="true" aria-label="Carregando">
      {Array.from({ length: linhas }, (_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-md bg-fundo-2" />
      ))}
    </div>
  );
}

export function ErroCarga({ erro, onTentar }: { erro: unknown; onTentar?: () => void }) {
  const msg = erro instanceof Error ? erro.message : "não consegui carregar";
  return (
    <Aviso tipo="erro">
      <span>{msg[0]?.toUpperCase() + msg.slice(1)}.</span>
      {onTentar && (
        <button type="button" onClick={onTentar} className="ml-2 font-semibold underline">
          Tentar de novo
        </button>
      )}
    </Aviso>
  );
}

export function mensagem(erro: unknown): string {
  const m = erro instanceof ErroApi || erro instanceof Error ? erro.message : "algo deu errado";
  return m[0]?.toUpperCase() + m.slice(1);
}

export function Vazio({ children, icone }: { children: React.ReactNode; icone?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-dashed border-borda-forte px-4 py-6 text-sm text-texto-2">
      {icone}
      <div>{children}</div>
    </div>
  );
}

// ------------------------------------------------------------------ formulário

export function Campo({ rotulo, dica, children, className, htmlFor }:
  { rotulo: React.ReactNode; dica?: React.ReactNode; children: React.ReactNode; className?: string; htmlFor?: string }) {
  return (
    <div className={cx("flex flex-col gap-1", className)}>
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-texto-2">{rotulo}</label>
      {children}
      {dica && <p className="text-xs text-texto-3">{dica}</p>}
    </div>
  );
}

const CAMPO = "h-9 w-full rounded-md border border-borda-forte bg-fundo px-2.5 text-sm text-texto placeholder:text-texto-3 disabled:opacity-60";

export const Entrada = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Entrada({ className, ...p }, ref) {
  return <input ref={ref} className={cx(CAMPO, className)} {...p} />;
});

export function Selecao({ className, children, ...p }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx(CAMPO, "pr-8", className)} {...p}>{children}</select>;
}

export function AreaTexto({ className, ...p }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx(CAMPO, "h-auto min-h-20 py-2", className)} {...p} />;
}

/** Campo com rótulo e id próprios, para não repetir useId em cada formulário. */
export function CampoEntrada({ rotulo, dica, className, ...p }: React.InputHTMLAttributes<HTMLInputElement> & { rotulo: string; dica?: React.ReactNode }) {
  const id = useId();
  return (
    <Campo rotulo={rotulo} dica={dica} htmlFor={id} className={className}>
      <Entrada id={id} {...p} />
    </Campo>
  );
}

export function CampoSelecao({ rotulo, dica, className, children, ...p }: React.SelectHTMLAttributes<HTMLSelectElement> & { rotulo: string; dica?: React.ReactNode }) {
  const id = useId();
  return (
    <Campo rotulo={rotulo} dica={dica} htmlFor={id} className={className}>
      <Selecao id={id} {...p}>{children}</Selecao>
    </Campo>
  );
}

// ------------------------------------------------------------------ abas e expansão

export function Abas<T extends string>({ abas, ativa, onTrocar, rotulo }:
  { abas: { id: T; rotulo: React.ReactNode }[]; ativa: T; onTrocar: (id: T) => void; rotulo: string }) {
  return (
    <div role="tablist" aria-label={rotulo} className="flex gap-1 overflow-x-auto border-b border-borda [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {abas.map((a) => (
        <button
          key={a.id}
          role="tab"
          type="button"
          aria-selected={a.id === ativa}
          onClick={() => onTrocar(a.id)}
          className={cx(
            "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium",
            a.id === ativa ? "border-marca text-texto" : "border-transparent text-texto-2 hover:text-texto",
          )}
        >
          {a.rotulo}
        </button>
      ))}
    </div>
  );
}

export function Expansivel({ resumo, children, aberto, className, onToggle }:
  { resumo: React.ReactNode; children: React.ReactNode; aberto?: boolean; className?: string; onToggle?: (aberto: boolean) => void }) {
  return (
    <details
      open={aberto}
      onToggle={(e) => onToggle?.((e.target as HTMLDetailsElement).open)}
      className={cx("group rounded-lg border border-borda bg-fundo", className)}
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm [&::-webkit-details-marker]:hidden">
        <ChevronDown className="size-4 shrink-0 text-texto-3 transition-transform group-open:rotate-180" aria-hidden />
        <div className="min-w-0 flex-1">{resumo}</div>
      </summary>
      <div className="border-t border-borda px-4 py-3">{children}</div>
    </details>
  );
}

const STATUS_DICAS: Record<string, string> = {
  "atrasada": "Obrigações com prazo vencido que precisam de atenção imediata",
  "dado_faltando": "Obrigações com dados incompletos ou não informados",
  "vence_logo": "Obrigações que vencem em até 30 dias",
  "gatilho": "Obrigações acionadas por um evento ou condição específica",
  "em_dia": "Obrigações que estão em conformidade e dentro do prazo",
};

export function Numero({ valor, rotulo, status, href, dica }: { valor: number | string; rotulo: string; status?: string; href?: string; dica?: string }) {
  const Descricao = dica ?? (status ? STATUS_DICAS[status] : undefined);
  const corpo = (
    <>
      <span className="flex items-center gap-1 text-[13px] font-medium text-texto-2">
        {rotulo}
        {Descricao && (
          <Dica descricao={Descricao} tamanho="numero" />
        )}
      </span>
      <span className="num text-3xl font-semibold leading-tight">{valor}</span>
    </>
  );
  const classe = cx(
    "flex flex-col gap-0.5 rounded-lg border border-borda bg-fundo px-4 py-3 shadow-cartao border-t-[3px]",
    status ? cor(status).topo : "border-t-marca",
  );
  return href ? (
    <Link href={href} className={cx(classe, "transition-colors hover:bg-fundo-2")}>{corpo}</Link>
  ) : (
    <div className={classe}>{corpo}</div>
  );
}
