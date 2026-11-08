"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookCheck, Building2, CalendarRange, ChartColumn, ClipboardList, FileBadge, FileSearch, Gavel, History, IdCard, Inbox, ListChecks, LogOut, Map, Menu,
  Moon, PanelLeftClose,
  PanelLeftOpen, Plus, Radar as IconeRadar, RotateCcw, ScrollText, Sparkles, Sun, Users, Workflow, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { api, dados } from "@/lib/api";
import { useCondicionantes, useMudancas, useNormasCandidatas, useRadar } from "@/lib/consultas";
import { dataBR, diasEntre, plural, usd } from "@/lib/formato";
import { RES_220, ZAS, useTorre } from "@/lib/torre";
import { useAvisar } from "./avisos";
import { Dialogo } from "./dialogo";
import { ImportarSigbm } from "./importar-sigbm";
import { Aviso, Botao, Entrada, Etiqueta, Selecao, TITULOS_DICAS, cx, mensagem } from "./ui";

const PAPEL: Record<string, string> = { admin: "TI", diretoria: "Diretoria", regulatorio: "Regulatório", gestor: "Gestor de área" };

function rotuloVisao(visao: string): string {
  return visao === "Diretoria (todos os ativos)" ? "Diretoria" : visao;
}

/** `dica` aparece ao passar o mouse; sem ela, o item usa a dica do título da tela (TITULOS_DICAS). */
type Item = { href: string; rotulo: string; icone: React.ReactNode; contador?: number; tom?: "perigo" | "marca"; dica?: string };
type Grupo = { titulo: string; itens: Item[]; dica?: string };

const DICA_ADMINISTRACAO = "Usuários, acessos e registro das ações no sistema";

function eCuradoriaMitra(plataforma: boolean, papel: string): boolean {
  return plataforma && papel === "regulatorio";
}

function useGrupos(): Grupo[] {
  const t = useTorre();
  const mudancas = useMudancas();
  const candidatas = useNormasCandidatas();
  const condicionantes = useCondicionantes("pendente");
  if (t.ti) {
    return [{ titulo: "Administração", itens: [
      { href: "/usuarios/", rotulo: "Usuários e acessos", icone: <Users className="size-4" /> },
      { href: "/auditoria/", rotulo: "Auditoria", icone: <ScrollText className="size-4" /> },
    ], dica: DICA_ADMINISTRACAO }];
  }
  const curadoria = eCuradoriaMitra(t.plataforma, t.eu.papel_efetivo);
  const grupos: Grupo[] = [
    { titulo: "Operação", itens: [
      { href: "/caixa/", rotulo: "Caixa de entrada", icone: <Inbox className="size-4" /> },
      { href: "/ativos/", rotulo: "Ativos", icone: t.empresa?.setor === "saude" ? <ListChecks className="size-4" /> : <Map className="size-4" /> },
      { href: "/entregas/", rotulo: "Entregas", icone: <ListChecks className="size-4" /> },
      { href: "/pergunte/", rotulo: "Assistente Mitra", icone: <Sparkles className="size-4" /> },
    ], dica: "Obrigações, ativos e entregas do dia a dia" },
    { titulo: "Regulatório", itens: [
      { href: "/regulatorio/mudancas/", rotulo: "Mudanças", icone: <Gavel className="size-4" />, contador: mudancas.data?.length || undefined, tom: "marca" },
      { href: "/regulatorio/radar/", rotulo: "Radar do DOU", icone: <IconeRadar className="size-4" /> },
      { href: "/regulatorio/transicao/", rotulo: "Transição e linha do tempo", icone: <CalendarRange className="size-4" /> },
      { href: "/regulatorio/cobertura/", rotulo: "Cobertura normativa", icone: <BookCheck className="size-4" /> },
      ...(t.plataforma ? [{ href: "/regulatorio/normas-candidatas/", rotulo: "Normas candidatas", icone: <FileSearch className="size-4" />,
        contador: candidatas.data?.contagem.relevante || undefined, tom: "marca" as const }] : []),
    ], dica: "Mudanças nas normas e o que se aplica à empresa" },
    { titulo: "Empresa", itens: [
      ...(t.plataforma ? [{ href: "/nova-empresa/", rotulo: "Nova empresa", icone: <Building2 className="size-4" /> }] : []),
      { href: "/instanciacao/", rotulo: "Instanciação", icone: <ClipboardList className="size-4" /> },
      { href: "/licencas/", rotulo: "Licenças e condicionantes", icone: <FileBadge className="size-4" />,
        contador: condicionantes.data?.length || undefined, tom: "marca", dica: TITULOS_DICAS["Licenças"] },
      { href: "/responsaveis/", rotulo: "Responsáveis e unidades", icone: <IdCard className="size-4" /> },
    ], dica: "Cadastro da empresa, licenças e responsáveis" },
    ...(curadoria ? [{ titulo: "Sobre", itens: [
      { href: "/sobre/mercado/", rotulo: "Mercado", icone: <ChartColumn className="size-4" /> },
      { href: "/sobre/como-funciona/", rotulo: "Como funciona", icone: <Workflow className="size-4" /> },
    ], dica: "Mercado e funcionamento da plataforma" }] : []),
  ];
  if (t.veTudo) grupos.push({ titulo: "Administração", itens: [{ href: "/auditoria/", rotulo: "Auditoria", icone: <ScrollText className="size-4" /> }], dica: "Registro das ações no sistema" });
  return grupos;
}

/** O que cada papel pode abrir; o resto volta para a tela inicial do papel. A fila de normas candidatas
 * é trabalho da curadoria Mitra: só a plataforma. */
export function telaPermitida(caminho: string, ti: boolean, veTudo: boolean, plataforma = false, curadoria = false): boolean {
  const c = caminho.endsWith("/") ? caminho : `${caminho}/`;
  if (ti) return c === "/usuarios/" || c === "/auditoria/";
  if (c === "/usuarios/") return false;
  if (c === "/auditoria/") return veTudo;
  if (c === "/regulatorio/normas-candidatas/") return plataforma;
  if (c === "/nova-empresa/") return plataforma;
  if (c.startsWith("/sobre/")) return curadoria;
  return true;
}

// ------------------------------------------------------------------ tema

function temaAtual(): "claro" | "escuro" {
  return typeof document !== "undefined" && document.documentElement.dataset.tema === "escuro" ? "escuro" : "claro";
}

function assinarTema(cb: () => void) {
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-tema"] });
  return () => obs.disconnect();
}

export function useTema() {
  const tema = useSyncExternalStore(assinarTema, temaAtual, () => "claro" as const);
  const trocar = () => {
    const novo = tema === "escuro" ? "claro" : "escuro";
    const raiz = document.documentElement;
    raiz.classList.add("tema-em-transicao");
    requestAnimationFrame(() => {
      raiz.dataset.tema = novo;
      window.setTimeout(() => raiz.classList.remove("tema-em-transicao"), 360);
    });
    try {
      localStorage.setItem("mitra_tema", novo);
    } catch {
      /* sem armazenamento: vale só nesta aba */
    }
  };
  return { tema, trocar };
}

export function Logo({ className }: { className?: string }) {
  const { tema } = useTema();
  // eslint-disable-next-line @next/next/no-img-element -- SVG da marca, sem otimização no export estático
  return <img src={tema === "escuro" ? "/logo_escuro.svg" : "/logo_claro.svg"} alt="Mitra" width={150} height={32} className={className} />;
}

// ------------------------------------------------------------------ menu

function Navegacao({ onNavegar }: { onNavegar?: () => void }) {
  const caminho = usePathname();
  const grupos = useGrupos();
  return (
    <nav aria-label="Telas da torre" className="space-y-5">
      {grupos.map((g) => (
        <div key={g.titulo}>
          <p className="px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-texto-3" title={g.dica}>{g.titulo}</p>
          <ul className="space-y-0.5">
            {g.itens.map((i) => {
              const ativo = caminho === i.href || caminho === i.href.slice(0, -1);
              return (
                <li key={i.href}>
                  <Link
                    href={i.href}
                    onClick={onNavegar}
                    title={i.dica ?? TITULOS_DICAS[i.rotulo]}
                    aria-current={ativo ? "page" : undefined}
                    className={cx(
                      "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm",
                      ativo ? "bg-marca-suave font-semibold text-marca" : "text-texto-2 hover:bg-fundo-3 hover:text-texto",
                    )}
                  >
                    {i.icone}
                    <span className="flex-1">{i.rotulo}</span>
                    {i.contador !== undefined && (
                      <span className={cx("num rounded-full px-1.5 text-[11px] font-semibold",
                        i.tom === "perigo" ? "bg-atrasada-fundo text-atrasada" : "bg-marca text-sobre-marca")}>
                        {i.contador}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function Controles() {
  const t = useTorre();
  const qc = useQueryClient();
  const avisar = useAvisar();
  const { tema, trocar } = useTema();
  const [importar, setImportar] = useState(false);
  const [recriar, setRecriar] = useState(false);
  const radar = useRadar();
  const recriarDemo = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/demo/recriar")),
    onSuccess: async () => {
      setRecriar(false);
      await qc.invalidateQueries();
      avisar("Demo recriada: entregas, decisões e empresas importadas voltaram ao estado inicial.");
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });
  const trocarVisao = useMutation({ mutationFn: t.trocarVisao, onError: (e) => avisar(mensagem(e), "erro") });
  const ia = radar.data?.ia;
  const saude = t.empresa?.setor === "saude";
  const viagens = saude
    ? [{ rotulo: "Demo", dia: t.hojeDemo, dica: `${dataBR(t.hojeDemo)}: o dia da demo` }]
    : [
        { rotulo: "Demo", dia: t.hojeDemo, dica: `${dataBR(t.hojeDemo)}: o dia da demo` },
        { rotulo: "Res. 220", dia: RES_220, dica: `${dataBR(RES_220)}: troca de norma` },
        { rotulo: "ZAS", dia: ZAS, dica: `${dataBR(ZAS)}: dia seguinte ao prazo da ZAS (ANM e NR-22)` },
      ];

  return (
    <div className="space-y-3 text-sm">
      <div className="rounded-lg border border-borda bg-fundo px-3 py-2.5">
        <p className="font-semibold leading-tight">{t.eu.nome}</p>
        <p className="mt-0.5 text-xs text-texto-2">
          {PAPEL[t.eu.papel] ?? t.eu.papel}
          {t.eu.area ? ` · ${t.eu.area}` : ""}
          {t.eu.teste ? " · Teste" : ""}
        </p>
      </div>

      {t.eu.visoes.length > 1 && (
        <label className="block">
          <span className="mb-1 block text-[13px] font-medium text-texto-2">Persona</span>
          <Selecao value={t.eu.visao} onChange={(e) => trocarVisao.mutate(e.target.value)} disabled={trocarVisao.isPending} aria-label="Persona">
            {t.eu.visoes.map((v) => <option key={v} value={v}>{rotuloVisao(v)}</option>)}
          </Selecao>
        </label>
      )}

      {!t.ti && t.empresas.length > 1 && (
        <label className="block">
          <span className="mb-1 block text-[13px] font-medium text-texto-2">Empresa</span>
          <Selecao value={t.empresa?.id ?? ""} onChange={(e) => t.setEmpresaId(Number(e.target.value))} aria-label="Empresa">
            {t.empresas.map((e) => <option key={e.id} value={e.id}>Empresa {e.id}{e.setor === "saude" ? " · saúde" : ""}{e.ficticia ? " · fictícia" : ""}</option>)}
          </Selecao>
        </label>
      )}

      {t.plataforma && t.veTudo && !saude && (
        <Botao className="w-full" icone={<Plus className="size-4" />} onClick={() => setImportar(true)}>
          Mineradora do SIGBM
        </Botao>
      )}

      {!t.ti && (
        <div>
          <label className="block">
            <span className="mb-1 block text-[13px] font-medium text-texto-2">Hoje</span>
            <Entrada type="date" value={t.hoje} onChange={(e) => e.target.value && t.setHoje(e.target.value)} aria-label="Hoje" />
          </label>
          <p className="mb-1 mt-2 text-xs text-texto-3">{saude ? "Data de referência" : "Viagem no tempo"}</p>
          <div className={cx("grid gap-1", saude ? "grid-cols-1" : "grid-cols-3")}>
            {viagens.map((v) => (
              <button
                key={v.rotulo}
                type="button"
                title={v.dica}
                aria-label={`${v.rotulo}: ${v.dica}`}
                aria-pressed={t.hoje === v.dia}
                onClick={() => t.setHoje(v.dia)}
                className={cx("h-8 rounded-md border text-xs font-medium",
                  t.hoje === v.dia ? "border-marca bg-marca-suave text-marca" : "border-borda-forte bg-fundo hover:bg-fundo-2")}
              >
                {v.rotulo}
              </button>
            ))}
          </div>
          {t.empresa?.monitorado_desde && (
            <p className="mt-2 text-xs text-texto-3">Monitorada desde {dataBR(t.empresa.monitorado_desde)}.</p>
          )}
        </div>
      )}

      {ia?.ligada && !t.ti && (
        <p className="text-xs text-texto-3">
          IA ligada · gasto hoje {usd(ia.gasto_hoje_usd, 3)}{ia.teto_dia_usd ? ` de ${usd(ia.teto_dia_usd, 2)}` : ""}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        <button type="button" onClick={trocar} title={tema === "escuro" ? "Usar tema claro" : "Usar tema escuro"}
          aria-label={tema === "escuro" ? "Usar tema claro" : "Usar tema escuro"}
          className="rounded-full border border-borda-forte bg-fundo p-2 text-texto-2 transition hover:bg-fundo-2 hover:text-texto active:scale-95">
          {tema === "escuro" ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
        </button>
        {t.eu.teste && (
          <Botao tamanho="p" icone={<RotateCcw className="size-3.5" />} onClick={() => setRecriar(true)}>Recriar demo</Botao>
        )}
        <Botao tamanho="p" icone={<LogOut className="size-3.5" />} onClick={() => void t.sair()}>Sair</Botao>
      </div>

      <ImportarSigbm aberto={importar} onFechar={() => setImportar(false)} />
      <Dialogo
        aberto={recriar}
        onFechar={() => setRecriar(false)}
        titulo="Recriar a demo?"
        rodape={<>
          <Botao onClick={() => setRecriar(false)}>Cancelar</Botao>
          <Botao variante="perigo" carregando={recriarDemo.isPending} onClick={() => recriarDemo.mutate()}>Recriar demo</Botao>
        </>}
      >
        <p className="text-sm text-texto-2">
          Apaga as entregas, decisões, comentários e empresas importadas, e volta as empresas fictícias ao estado inicial.
          As contas de acesso ficam.
        </p>
      </Dialogo>
    </div>
  );
}

function Cabecalho() {
  const t = useTorre();
  if (t.ti) return null;
  const viajando = t.empresa?.setor !== "saude" && t.hoje > t.hojeDemo && !t.empresa?.monitorado_desde;
  if (!viajando && !t.soLeitura) return null;
  return (
    <div className="mb-6">
      {t.soLeitura && (
        <p className="mb-3" data-testid="so-leitura">
          <Etiqueta title="A equipe Mitra acompanha a empresa, mas quem registra entrega, comenta e corrige o cadastro é a própria empresa.">
            visão da plataforma: só leitura
          </Etiqueta>
        </p>
      )}
      {viajando && (
        <Aviso tipo="info" icone={<History className="size-4 text-gatilho" />}>
          Viagem no tempo: {dataBR(t.hoje)}, {plural(diasEntre(t.hojeDemo, t.hoje), "dia", "dias")} depois da demo. As entregas da
          demo vão até {dataBR(t.hojeDemo)}; o que venceu depois disso aparece atrasado porque ninguém registrou a entrega.
          O ponto aqui é ver o que a torre passa a cobrar, e de qual norma.
        </Aviso>
      )}
    </div>
  );
}

export function Moldura({ children }: { children: React.ReactNode }) {
  const t = useTorre();
  const caminho = usePathname();
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  const [sidebarOculta, setSidebarOculta] = useState(false);
  const permitida = telaPermitida(caminho, t.ti, t.veTudo, t.plataforma, eCuradoriaMitra(t.plataforma, t.eu.papel_efetivo));

  useEffect(() => {
    if (!permitida) router.replace(t.ti ? "/usuarios/" : "/caixa/");
  }, [permitida, t.ti, router]);

  return (
    <div className={cx(
      "min-h-dvh lg:grid lg:transition-[grid-template-columns] lg:duration-500 lg:ease-[cubic-bezier(0.22,1,0.36,1)]",
      sidebarOculta ? "lg:grid-cols-[0px_1fr]" : "lg:grid-cols-[272px_1fr]",
    )}>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-borda bg-fundo/95 px-4 py-2.5 backdrop-blur lg:hidden">
        <Logo className="h-7 w-auto" />
        <button type="button" onClick={() => setMenu(true)} aria-label="Abrir o menu" className="rounded-md p-2 hover:bg-fundo-2">
          <Menu className="size-5" />
        </button>
      </header>

      {menu && <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setMenu(false)} aria-hidden />}
      {sidebarOculta && (
        <button type="button" onClick={() => setSidebarOculta(false)} aria-label="Mostrar barra lateral" title="Mostrar barra lateral"
          className="fixed left-4 top-4 z-30 hidden rounded-full border border-borda-forte bg-fundo p-2 text-texto-2 shadow-cartao transition hover:bg-fundo-2 hover:text-texto lg:inline-flex">
          <PanelLeftOpen className="size-4" aria-hidden />
        </button>
      )}
      <aside
        className={cx(
          "fixed inset-y-0 left-0 z-50 flex w-[288px] max-w-[85vw] flex-col gap-6 overflow-y-auto border-r border-borda bg-lateral px-3 py-4 transition-[transform,opacity] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] lg:sticky lg:top-0 lg:z-auto lg:h-dvh lg:w-[272px] lg:max-w-none lg:min-w-0",
          sidebarOculta ? "lg:-translate-x-full lg:opacity-0" : "lg:translate-x-0 lg:opacity-100",
          menu ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Menu da torre"
      >
        <div className="flex items-center justify-between px-1.5">
          <Link href={t.ti ? "/usuarios/" : "/caixa/"} onClick={() => setMenu(false)}>
            <Logo className="h-[30px] w-auto" />
          </Link>
          <button type="button" onClick={() => setMenu(false)} aria-label="Fechar o menu" className="rounded-md p-1.5 hover:bg-fundo-3 lg:hidden">
            <X className="size-5" />
          </button>
          <button type="button" onClick={() => setSidebarOculta(true)} aria-label="Ocultar barra lateral" title="Ocultar barra lateral"
            className="hidden rounded-md p-1.5 text-texto-2 transition hover:bg-fundo-3 hover:text-texto lg:inline-flex">
            <PanelLeftClose className="size-5" aria-hidden />
          </button>
        </div>
        <Navegacao onNavegar={() => setMenu(false)} />
        <div className="mt-auto border-t border-borda pt-4">
          <Controles />
        </div>
      </aside>

      <main className="min-w-0 px-4 py-5 sm:px-6 lg:px-10 lg:py-8">
        <div className="mx-auto max-w-[1240px]">
          <Cabecalho />
          {!permitida ? null : t.ti || t.empresa ? children : (
            <Aviso tipo="info">Nenhuma empresa visível para esta conta ainda. Peça à curadoria da Mitra para montar a torre da sua empresa.</Aviso>
          )}
        </div>
      </main>
    </div>
  );
}
