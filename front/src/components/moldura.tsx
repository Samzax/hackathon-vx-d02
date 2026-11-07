"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookCheck, CalendarRange, ChartColumn, FileSearch, Gavel, History, Inbox, ListChecks, LogOut, Map, Menu, Moon, Plus,
  Radar as IconeRadar, RotateCcw, ScrollText, Sun, Users, Workflow, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { api, dados } from "@/lib/api";
import { useAtivos, useMudancas, useNormasCandidatas, usePainel, useRadar } from "@/lib/consultas";
import { dataBR, diasEntre, plural, usd } from "@/lib/formato";
import { RES_220, ZAS, useTorre } from "@/lib/torre";
import { useAvisar } from "./avisos";
import { Dialogo } from "./dialogo";
import { ImportarSigbm } from "./importar-sigbm";
import { Aviso, Botao, Entrada, Etiqueta, Selecao, cx, mensagem } from "./ui";

const PAPEL: Record<string, string> = { admin: "TI", diretoria: "Diretoria", regulatorio: "Regulatório", gestor: "Gestor de área" };

type Item = { href: string; rotulo: string; icone: React.ReactNode; contador?: number; tom?: "perigo" | "marca" };
type Grupo = { titulo: string; itens: Item[] };

function useGrupos(): Grupo[] {
  const t = useTorre();
  const mudancas = useMudancas();
  const painel = usePainel();
  const candidatas = useNormasCandidatas();
  if (t.ti) {
    return [{ titulo: "Administração", itens: [
      { href: "/usuarios/", rotulo: "Usuários e acessos", icone: <Users className="size-4" /> },
      { href: "/auditoria/", rotulo: "Auditoria", icone: <ScrollText className="size-4" /> },
    ] }];
  }
  const atrasadas = painel.data?.contagem.atrasada ?? 0;
  const grupos: Grupo[] = [
    { titulo: "Operação", itens: [
      { href: "/caixa/", rotulo: "Caixa de entrada", icone: <Inbox className="size-4" />, contador: atrasadas || undefined, tom: "perigo" },
      { href: "/ativos/", rotulo: "Ativos", icone: <Map className="size-4" /> },
      { href: "/entregas/", rotulo: "Entregas", icone: <ListChecks className="size-4" /> },
    ] },
    { titulo: "Regulatório", itens: [
      { href: "/regulatorio/mudancas/", rotulo: "Mudanças", icone: <Gavel className="size-4" />, contador: mudancas.data?.length || undefined, tom: "marca" },
      { href: "/regulatorio/radar/", rotulo: "Radar do DOU", icone: <IconeRadar className="size-4" /> },
      { href: "/regulatorio/transicao/", rotulo: "Transição e linha do tempo", icone: <CalendarRange className="size-4" /> },
      { href: "/regulatorio/cobertura/", rotulo: "Cobertura normativa", icone: <BookCheck className="size-4" /> },
      ...(t.plataforma ? [{ href: "/regulatorio/normas-candidatas/", rotulo: "Normas candidatas", icone: <FileSearch className="size-4" />,
        contador: candidatas.data?.contagem.relevante || undefined, tom: "marca" as const }] : []),
    ] },
    { titulo: "Sobre", itens: [
      { href: "/sobre/mercado/", rotulo: "Mercado", icone: <ChartColumn className="size-4" /> },
      { href: "/sobre/como-funciona/", rotulo: "Como funciona", icone: <Workflow className="size-4" /> },
    ] },
  ];
  if (t.veTudo) grupos.push({ titulo: "Administração", itens: [{ href: "/auditoria/", rotulo: "Auditoria", icone: <ScrollText className="size-4" /> }] });
  return grupos;
}

/** O que cada papel pode abrir; o resto volta para a tela inicial do papel. A fila de normas candidatas
 * é trabalho da curadoria RegulaIA: só a plataforma. */
export function telaPermitida(caminho: string, ti: boolean, veTudo: boolean, plataforma = false): boolean {
  const c = caminho.endsWith("/") ? caminho : `${caminho}/`;
  if (ti) return c === "/usuarios/" || c === "/auditoria/";
  if (c === "/usuarios/") return false;
  if (c === "/auditoria/") return veTudo;
  if (c === "/regulatorio/normas-candidatas/") return plataforma;
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
    document.documentElement.dataset.tema = novo;
    try {
      localStorage.setItem("regulaia_tema", novo);
    } catch {
      /* sem armazenamento: vale só nesta aba */
    }
  };
  return { tema, trocar };
}

export function Logo({ className }: { className?: string }) {
  const { tema } = useTema();
  // eslint-disable-next-line @next/next/no-img-element -- SVG da marca, sem otimização no export estático
  return <img src={tema === "escuro" ? "/logo_escuro.svg" : "/logo_claro.svg"} alt="RegulaIA" width={150} height={30} className={className} />;
}

// ------------------------------------------------------------------ menu

function Navegacao({ onNavegar }: { onNavegar?: () => void }) {
  const caminho = usePathname();
  const grupos = useGrupos();
  return (
    <nav aria-label="Telas da torre" className="space-y-5">
      {grupos.map((g) => (
        <div key={g.titulo}>
          <p className="px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-texto-3">{g.titulo}</p>
          <ul className="space-y-0.5">
            {g.itens.map((i) => {
              const ativo = caminho === i.href || caminho === i.href.slice(0, -1);
              return (
                <li key={i.href}>
                  <Link
                    href={i.href}
                    onClick={onNavegar}
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

  return (
    <div className="space-y-3 text-sm">
      <div className="rounded-lg border border-borda bg-fundo px-3 py-2.5">
        <p className="font-semibold leading-tight">{t.eu.nome}</p>
        <p className="mt-0.5 text-xs text-texto-2">
          {PAPEL[t.eu.papel] ?? t.eu.papel}
          {t.eu.area ? ` · ${t.eu.area}` : ""}
          {t.eu.teste ? " · conta de teste" : ""}
        </p>
        {t.eu.empresa && <p className="mt-0.5 text-xs text-texto-3">{t.eu.empresa}</p>}
      </div>

      {t.eu.visoes.length > 1 && (
        <label className="block">
          <span className="mb-1 block text-[13px] font-medium text-texto-2">Quem está olhando</span>
          <Selecao value={t.eu.visao} onChange={(e) => trocarVisao.mutate(e.target.value)} disabled={trocarVisao.isPending} aria-label="Quem está olhando">
            {t.eu.visoes.map((v) => <option key={v} value={v}>{v}</option>)}
          </Selecao>
        </label>
      )}

      {!t.ti && t.empresas.length > 1 && (
        <label className="block">
          <span className="mb-1 block text-[13px] font-medium text-texto-2">Empresa</span>
          <Selecao value={t.empresa?.id ?? ""} onChange={(e) => t.setEmpresaId(Number(e.target.value))} aria-label="Empresa">
            {t.empresas.map((e) => <option key={e.id} value={e.id}>{e.nome}{e.ficticia ? " · fictícia" : ""}</option>)}
          </Selecao>
        </label>
      )}

      {t.plataforma && t.veTudo && (
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
          <p className="mb-1 mt-2 text-xs text-texto-3">Viagem no tempo</p>
          <div className="grid grid-cols-3 gap-1">
            {[
              { rotulo: "Demo", dia: t.hojeDemo, dica: `${dataBR(t.hojeDemo)}: o dia da demo` },
              { rotulo: "Res. 220", dia: RES_220, dica: `${dataBR(RES_220)}: troca de norma` },
              { rotulo: "ZAS", dia: ZAS, dica: `${dataBR(ZAS)}: dia seguinte ao prazo da ZAS (ANM e NR-22)` },
            ].map((v) => (
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

      {ia && !t.ti && (
        <p className="text-xs text-texto-3">
          {ia.ligada
            ? `IA ligada · gasto hoje ${usd(ia.gasto_hoje_usd, 3)}${ia.teto_dia_usd ? ` de ${usd(ia.teto_dia_usd, 2)}` : ""}`
            : "IA desligada: só regra e respostas em cache"}
        </p>
      )}

      <div className="flex flex-wrap gap-1.5 pt-1">
        {t.eu.teste && (
          <Botao tamanho="p" icone={<RotateCcw className="size-3.5" />} onClick={() => setRecriar(true)}>Recriar demo</Botao>
        )}
        <Botao tamanho="p" onClick={trocar} aria-label={tema === "escuro" ? "Usar tema claro" : "Usar tema escuro"}
          icone={tema === "escuro" ? <Sun className="size-3.5" /> : <Moon className="size-3.5" />}>
          {tema === "escuro" ? "Claro" : "Escuro"}
        </Botao>
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
          Apaga as entregas, decisões, comentários e empresas importadas, e volta a Mineradora Serra Azul ao estado inicial.
          As contas de acesso ficam.
        </p>
      </Dialogo>
    </div>
  );
}

function Cabecalho() {
  const t = useTorre();
  const ativos = useAtivos();
  if (t.ti) return null;
  const viajando = t.hoje > t.hojeDemo && !t.empresa?.monitorado_desde;
  return (
    <div className="mb-6">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-borda pb-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-texto-3">Torre de controle regulatória</p>
          <p className="truncate text-xl font-semibold" data-testid="empresa">{t.empresa?.nome}</p>
        </div>
        <div className="text-[13px] text-texto-2 sm:text-right">
          <p className="num font-semibold text-texto" data-testid="hoje">{dataBR(t.hoje)}</p>
          <p>
            {t.eu.visao}
            {ativos.data ? ` · ${plural(ativos.data.length, "ativo", "ativos")}` : ""}
          </p>
          {t.soLeitura && (
            <p className="mt-1" data-testid="so-leitura">
              <Etiqueta title="A equipe RegulaIA acompanha a empresa, mas quem registra entrega, comenta e corrige o cadastro é a própria empresa.">
                visão da plataforma: só leitura
              </Etiqueta>
            </p>
          )}
        </div>
      </div>
      {viajando && (
        <Aviso tipo="info" className="mt-3" icone={<History className="size-4 text-gatilho" />}>
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
  const permitida = telaPermitida(caminho, t.ti, t.veTudo, t.plataforma);

  useEffect(() => {
    if (!permitida) router.replace(t.ti ? "/usuarios/" : "/caixa/");
  }, [permitida, t.ti, router]);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[272px_1fr]">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-borda bg-fundo/95 px-4 py-2.5 backdrop-blur lg:hidden">
        <Logo className="h-7 w-auto" />
        <button type="button" onClick={() => setMenu(true)} aria-label="Abrir o menu" className="rounded-md p-2 hover:bg-fundo-2">
          <Menu className="size-5" />
        </button>
      </header>

      {menu && <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setMenu(false)} aria-hidden />}
      <aside
        className={cx(
          "fixed inset-y-0 left-0 z-50 flex w-[288px] max-w-[85vw] flex-col gap-6 overflow-y-auto border-r border-borda bg-lateral px-3 py-4 transition-transform lg:sticky lg:top-0 lg:z-auto lg:h-dvh lg:w-auto lg:max-w-none lg:translate-x-0",
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
            <Aviso tipo="info">Nenhuma empresa visível para esta conta ainda. Peça à curadoria da RegulaIA para montar a torre da sua empresa.</Aviso>
          )}
        </div>
      </main>
    </div>
  );
}
