"use client";

import { Moldura } from "@/components/moldura";
import { Carregando, ErroCarga } from "@/components/ui";
import { TorreProvider } from "@/lib/torre";

export default function LayoutTorre({ children }: { children: React.ReactNode }) {
  return (
    <TorreProvider
      carregando={<div className="mx-auto max-w-5xl p-8"><Carregando linhas={6} /></div>}
      erro={(e) => <div className="mx-auto max-w-3xl p-8"><ErroCarga erro={e} onTentar={() => location.reload()} /></div>}
    >
      <Moldura>{children}</Moldura>
    </TorreProvider>
  );
}
