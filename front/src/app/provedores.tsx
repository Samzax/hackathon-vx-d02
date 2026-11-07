"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Avisos } from "@/components/avisos";
import { ErroApi } from "@/lib/api";

export function Provedores({ children }: { children: React.ReactNode }) {
  const [cliente] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            refetchOnWindowFocus: false,
            // 401/403/404 não melhoram tentando de novo
            retry: (n, erro) => !(erro instanceof ErroApi && [401, 403, 404, 422].includes(erro.status)) && n < 2,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={cliente}>
      <Avisos>{children}</Avisos>
    </QueryClientProvider>
  );
}
