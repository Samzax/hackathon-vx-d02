import type { NextConfig } from "next";

// Exportado estático (front/out): em produção a própria API serve estes arquivos na mesma origem,
// então o cookie de sessão e o CSRF funcionam sem CORS. Em dev, Next na 3000 e API na 8000.
const config: NextConfig = {
  output: "export",
  trailingSlash: true, // /caixa/index.html: o StaticFiles da API serve a pasta sem regra extra
  images: { unoptimized: true },
  reactStrictMode: true,
  poweredByHeader: false,
};

export default config;
