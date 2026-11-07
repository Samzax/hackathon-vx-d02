"use client";

// Mapa dos ativos (Leaflet). Só é carregado no navegador: next/dynamic com ssr: false em quem usa.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { ROTULO } from "@/lib/status";
import { useTema } from "./moldura";

export type Ponto = { id: number; codigo: string; nome: string; tipo: string; status: string; posicao: [number, number] };

const VAR: Record<string, string> = { atrasada: "--atrasada", dado_faltando: "--faltando", vence_logo: "--vence-marca", em_dia: "--emdia" };
// ladrilhos do OpenStreetMap (sem chave); o tema escuro inverte as cores no CSS (globals.css)
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

function variavel(nome: string, padrao: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || padrao;
}

function escapar(t: string): string {
  return t.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

function corDe(status: string): string {
  return variavel(VAR[status] ?? "--emdia", "#2b8452");
}

export default function Mapa({ pontos, escolhido, onEscolher }: { pontos: Ponto[]; escolhido: number | null; onEscolher: (id: number) => void }) {
  const caixa = useRef<HTMLDivElement>(null);
  const mapa = useRef<L.Map | null>(null);
  const camada = useRef<L.LayerGroup | null>(null);
  const { tema } = useTema();
  const escolher = useRef(onEscolher);
  useEffect(() => { escolher.current = onEscolher; }, [onEscolher]);

  useEffect(() => {
    if (!caixa.current || mapa.current) return;
    const m = L.map(caixa.current, { scrollWheelZoom: false, attributionControl: true });
    mapa.current = m;
    L.tileLayer(TILES, {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">colaboradores do OpenStreetMap</a>',
    }).addTo(m);
    camada.current = L.layerGroup().addTo(m);
    return () => { m.remove(); mapa.current = null; camada.current = null; };
  }, []);

  useEffect(() => {
    const m = mapa.current;
    const g = camada.current;
    if (!m || !g) return;
    g.clearLayers();
    for (const p of pontos) {
      const marca = L.circleMarker(p.posicao, {
        radius: p.tipo === "barragem" ? 9 : 6.5,
        color: p.id === escolhido ? variavel("--texto", "#1b2128") : "#ffffff",
        weight: p.id === escolhido ? 3 : 1.5,
        fillColor: corDe(p.status),
        fillOpacity: 0.95,
      });
      marca.bindTooltip(p.codigo, { permanent: true, direction: "top", offset: [0, -8], className: "rotulo-ativo" });
      marca.bindPopup(`<strong>${escapar(p.codigo)} · ${escapar(p.nome)}</strong><br>${escapar(ROTULO[p.status] ?? p.status)}`);
      marca.on("click", () => escolher.current(p.id));
      marca.addTo(g);
    }
    // a cor vem do tema: troca de tema redesenha
  }, [pontos, escolhido, tema]);

  // enquadra todos os pontos quando a lista muda (escolher um ponto não mexe no enquadramento)
  const enquadrados = pontos.map((p) => p.codigo).join();
  useEffect(() => {
    const m = mapa.current;
    if (m && pontos.length) m.fitBounds(L.latLngBounds(pontos.map((p) => p.posicao)), { padding: [36, 36], maxZoom: 13 });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- só quando muda o conjunto de ativos
  }, [enquadrados]);

  return <div ref={caixa} className="h-[320px] w-full overflow-hidden rounded-lg border border-borda" role="region" aria-label="Mapa dos ativos" />;
}
