import Link from 'next/link';
import { ArrowRight, CalendarDays, ClipboardCheck, FileText, Gavel, LayoutDashboard, MapPinned } from 'lucide-react';

const kpis = [
  { label: 'Atrasada', value: '—', color: '#c62828' },
  { label: 'Dado faltando', value: '—', color: '#5b6b78' },
  { label: 'Vence em breve', value: '—', color: '#b45309' },
  { label: 'Em dia', value: '—', color: '#15803d' },
  { label: 'Por gatilho', value: '—', color: '#1d4ed8' }
];

const nav = [
  { href: '/', label: 'Caixa de entrada', icon: LayoutDashboard },
  { href: '/ativos', label: 'Ativos', icon: MapPinned },
  { href: '/entregas', label: 'Entregas', icon: ClipboardCheck },
  { href: '/regulatorio', label: 'Regulatório', icon: Gavel },
  { href: '/sobre', label: 'Sobre · Mercado', icon: FileText }
];

export default function Home() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="logo" aria-hidden="true">M</div><strong>Mitra</strong></div>
        <nav className="nav" aria-label="Navegação principal">
          {nav.map(({ href, label, icon: Icon }) => <Link href={href} key={href}><Icon size={16} aria-hidden="true" /> {label}</Link>)}
        </nav>
        <div className="demo-card"><strong>Visitante da demo</strong>Diretoria · conta de teste</div>
      </aside>
      <main className="main">
        <header className="header">
          <div><div className="eyebrow">Torre de controle regulatória</div><h1>Mineradora Serra Azul</h1></div>
          <div className="header-meta">07/11/2026<br />Diretoria (todos os ativos) · — ativos</div>
        </header>
        <section className="grid kpis" aria-label="Resumo de obrigações">
          {kpis.map((item) => <article className="card kpi" style={{ '--status': item.color } as React.CSSProperties} key={item.label}><span>{item.label}</span><strong>{item.value}</strong></article>)}
        </section>
        <section className="grid content">
          <article className="card decision"><div className="eyebrow">Aguardando decisão</div><h2>O que precisa de decisão ou ação</h2><p><span className="status-dot" />A conexão com a API existente ainda não está disponível neste checkout.</p><div className="decision-row"><span>Os dados reais aparecerão aqui quando o contrato da API estiver configurado.</span><button className="action" type="button">Decidir <ArrowRight size={16} /></button></div></article>
          <article className="card dashed"><div><CalendarDays size={28} aria-hidden="true" /><h2>Chegou um documento da operação?</h2><p>FIR, laudo, recibo do SIGBM ou boletim.</p><button className="action" type="button">Ler documento</button></div></article>
        </section>
      </main>
    </div>
  );
}
