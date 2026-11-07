import "@fontsource-variable/inter";
import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Provedores } from "./provedores";

export const metadata: Metadata = {
  title: { default: "Mitra · Torre de controle regulatória", template: "%s · Mitra" },
  description: "Cada obrigação de cada ativo, com a norma, o trecho literal e o prazo.",
  icons: { icon: "/marca.svg" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1318" },
  ],
};

// escolhe o tema antes de pintar (o salvo pela pessoa, ou o do sistema): sem piscar claro no escuro
const TEMA = `try{var t=localStorage.getItem("mitra_tema")||localStorage.getItem("regulaia_tema");if(t!=="claro"&&t!=="escuro"){t=matchMedia("(prefers-color-scheme: dark)").matches?"escuro":"claro"}document.documentElement.dataset.tema=t}catch(e){document.documentElement.dataset.tema="claro"}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: TEMA }} />
      </head>
      <body className="min-h-dvh antialiased">
        <Provedores>{children}</Provedores>
      </body>
    </html>
  );
}
