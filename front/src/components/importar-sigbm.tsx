"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { api, dados } from "@/lib/api";
import { dataBR, plural } from "@/lib/formato";
import { useTorre } from "@/lib/torre";
import { useAvisar } from "./avisos";
import { Dialogo } from "./dialogo";
import { Aviso, Botao, CampoEntrada, Entrada, cx, mensagem } from "./ui";

/** Sua mineradora em 30 segundos: busca no SIGBM público e monta a torre (curadoria da plataforma). */
export function ImportarSigbm({ aberto, onFechar }: { aberto: boolean; onFechar: () => void }) {
  const t = useTorre();
  const qc = useQueryClient();
  const avisar = useAvisar();
  const [termo, setTermo] = useState("");
  const [busca, setBusca] = useState("");
  const [cnpj, setCnpj] = useState<string | null>(null);
  const [soPnsb, setSoPnsb] = useState(true);
  const [desde, setDesde] = useState(t.hoje);
  const achadas = useQuery({
    queryKey: ["sigbm", busca],
    queryFn: () => dados(api.GET("/api/v1/sigbm/busca", { params: { query: { termo: busca } } })),
    enabled: busca.length >= 3,
  });
  const escolhida = achadas.data?.achadas.find((a) => a.cnpj === cnpj) ?? null;
  const montar = useMutation({
    mutationFn: () => dados(api.POST("/api/v1/sigbm/importar", {
      body: { cnpj: escolhida!.cnpj, monitorado_desde: desde, so_pnsb: soPnsb && escolhida!.na_pnsb > 0 },
    })),
    onSuccess: async (r) => {
      await qc.invalidateQueries({ queryKey: ["empresas"] });
      t.setEmpresaId(r.empresa_id);
      avisar(`Torre de ${escolhida!.nome} montada a partir do SIGBM.`);
      onFechar();
    },
    onError: (e) => avisar(mensagem(e), "erro"),
  });

  return (
    <Dialogo aberto={aberto} onFechar={onFechar} titulo="Sua mineradora em 30 segundos" largura="lg"
      rodape={<>
        <Botao onClick={onFechar}>Cancelar</Botao>
        <Botao variante="primario" disabled={!escolhida} carregando={montar.isPending} onClick={() => montar.mutate()}>
          {escolhida ? `Montar a torre de ${escolhida.nome}` : "Escolha uma empresa"}
        </Botao>
      </>}>
      <p className="text-sm text-texto-2">
        Barragens reais do SIGBM {achadas.data ? `(exportação pública de ${dataBR(achadas.data.exportado_em)})` : ""}, só de
        empresas (CNPJ). A torre monta as obrigações pelas regras do cadastro; o que o SIGBM não informa fica como
        <strong> dado faltando</strong>, para a empresa preencher. Nada é presumido.
      </p>
      <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); setBusca(termo.trim()); setCnpj(null); }}>
        <Entrada value={termo} onChange={(e) => setTermo(e.target.value)} placeholder="CNPJ ou nome: 33.592.510/0001-54, Vale, Samarco…"
          aria-label="CNPJ ou nome da empresa" />
        <Botao type="submit" icone={<Search className="size-4" />} disabled={termo.trim().length < 3}>Buscar</Botao>
      </form>
      {achadas.isFetching && <p className="mt-3 text-sm text-texto-2">Buscando no SIGBM…</p>}
      {achadas.error && <Aviso tipo="erro" className="mt-3">{mensagem(achadas.error)}</Aviso>}
      {achadas.data && !achadas.data.achadas.length && (
        <Aviso tipo="atencao" className="mt-3">Nenhuma empresa com barragem no SIGBM com esse CNPJ ou nome.</Aviso>
      )}
      {!!achadas.data?.achadas.length && (
        <ul className="mt-3 max-h-64 space-y-1 overflow-y-auto" role="radiogroup" aria-label="Empresa">
          {achadas.data.achadas.map((a) => (
            <li key={a.cnpj}>
              <button type="button" role="radio" aria-checked={cnpj === a.cnpj} onClick={() => setCnpj(a.cnpj)}
                className={cx("w-full rounded-md border px-3 py-2 text-left text-sm",
                  cnpj === a.cnpj ? "border-marca bg-marca-suave" : "border-borda hover:bg-fundo-2")}>
                <span className="font-medium">{a.nome}</span>
                <span className="block text-xs text-texto-2">
                  {a.cnpj} · {plural(a.barragens, "barragem", "barragens")} ({a.na_pnsb} na PNSB)
                  {a.com_alerta ? ` · ${plural(a.com_alerta, "com alerta", "com alerta")}` : ""} · {a.ufs.join(", ")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {escolhida && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={soPnsb && escolhida.na_pnsb > 0} disabled={!escolhida.na_pnsb}
              onChange={(e) => setSoPnsb(e.target.checked)} className="size-4 accent-[var(--marca)]" />
            Só as barragens na PNSB (onde valem as obrigações da Res. 95)
          </label>
          <CampoEntrada rotulo="Começar a cobrar a partir de" type="date" value={desde} onChange={(e) => setDesde(e.target.value)}
            dica="O que venceu antes não aparece como atraso: a torre não sabe o que já foi entregue." />
        </div>
      )}
    </Dialogo>
  );
}
