import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Mitra · Torre de controle regulatória',
  description: 'Torre de controle regulatória para operações de mineração'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
