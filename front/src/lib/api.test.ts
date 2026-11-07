import { describe, expect, it, vi } from "vitest";
import { CABECALHO_CSRF, criarCliente, dados, enviarArquivo, ErroApi, lerCookie, mensagemDe, texto, urlDe } from "./api";

const COOKIES = "outro=1; mitra_csrf=abc%3D123; tema=escuro";

function fetchFalso(status = 200, corpo: unknown = { ok: true }) {
  return vi.fn(async (entrada: Request | string | URL, init?: RequestInit) => {
    void entrada;
    void init;
    return new Response(JSON.stringify(corpo), { status, headers: { "content-type": "application/json" } });
  });
}

function pedido(f: ReturnType<typeof fetchFalso>): Request {
  return f.mock.calls[0]![0] as Request;
}

describe("cookie", () => {
  it("lê o valor do cookie pelo nome", () => {
    expect(lerCookie("mitra_csrf", COOKIES)).toBe("abc=123");
    expect(lerCookie("nao_tem", COOKIES)).toBeNull();
    expect(lerCookie("mitra_csrf", "")).toBeNull();
  });
});

describe("cliente", () => {
  it("toda escrita leva o X-CSRF-Token do cookie e o cookie de sessão", async () => {
    const f = fetchFalso(201, { id: 1 });
    const c = criarCliente("http://api", f as unknown as typeof fetch, () => COOKIES);
    await c.POST("/api/v1/comentarios", { body: { ativo_id: 3, texto: "oi" } });
    const r = pedido(f);
    expect(r.method).toBe("POST");
    expect(r.headers.get(CABECALHO_CSRF)).toBe("abc=123");
    expect(r.credentials).toBe("include");
    expect(r.url).toBe("http://api/api/v1/comentarios");
  });

  it("leitura não manda CSRF, mas manda o cookie", async () => {
    const f = fetchFalso(200, []);
    const c = criarCliente("http://api", f as unknown as typeof fetch, () => COOKIES);
    await c.GET("/api/v1/empresas/{empresa_id}/painel", { params: { path: { empresa_id: 1 }, query: { hoje: "2027-08-02" } } });
    const r = pedido(f);
    expect(r.headers.get(CABECALHO_CSRF)).toBeNull();
    expect(r.credentials).toBe("include");
    expect(r.url).toBe("http://api/api/v1/empresas/1/painel?hoje=2027-08-02");
  });

  it("dados() devolve o corpo ou lança ErroApi com a mensagem da API", async () => {
    const ok = criarCliente("http://api", fetchFalso(200, [{ id: 1 }]) as unknown as typeof fetch, () => "");
    await expect(dados(ok.GET("/api/v1/empresas"))).resolves.toEqual([{ id: 1 }]);
    const negado = criarCliente("http://api",
      fetchFalso(403, { detail: "só a TI administra contas" }) as unknown as typeof fetch, () => "");
    const erro = await dados(negado.GET("/api/v1/usuarios")).catch((e) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.status).toBe(403);
    expect(erro.message).toBe("só a TI administra contas");
  });

  it("sem rede vira ErroApi com status 0", async () => {
    const c = criarCliente("http://api", (async () => { throw new TypeError("failed"); }) as unknown as typeof fetch);
    const erro = await dados(c.GET("/api/v1/empresas")).catch((e) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.status).toBe(0);
  });
});

describe("mensagens de erro", () => {
  it("validação do FastAPI vira uma frase por campo", () => {
    expect(mensagemDe([{ loc: ["body", "senha"], msg: "String should have at least 8 characters" }], 422))
      .toBe("senha: String should have at least 8 characters");
    expect(mensagemDe(undefined, 401)).toBe("entre na torre para continuar");
    expect(mensagemDe("", 500)).toMatch(/tente de novo/);
  });
});

describe("rotas sem JSON e envio de arquivo", () => {
  it("monta a consulta com listas repetidas e sem vazios", () => {
    expect(urlDe("/api/v1/empresas/1/planilha", { status: ["atrasada", "vence_logo"], busca: "", hoje: "2026-11-07" }, ""))
      .toBe("/api/v1/empresas/1/planilha?status=atrasada&status=vence_logo&hoje=2026-11-07");
  });

  it("texto() lê Markdown e lança com o detalhe da API", async () => {
    const md = vi.fn(async (url: string, init?: RequestInit) => { void url; void init; return new Response("# Boletim", { status: 200 }); });
    await expect(texto("/api/v1/empresas/1/boletim", {}, md as unknown as typeof fetch)).resolves.toBe("# Boletim");
    expect(md.mock.calls[0]![1]).toMatchObject({ credentials: "include" });
    const negado = fetchFalso(404, { detail: "empresa 9 não existe" });
    await expect(texto("/x", {}, negado as unknown as typeof fetch)).rejects.toThrow("empresa 9 não existe");
  });

  it("enviarArquivo() manda multipart com CSRF e cookie", async () => {
    const f = fetchFalso(200, { completa: true });
    const r = await enviarArquivo<{ completa: boolean }>("/api/v1/evidencias/leitura", { empresa_id: 1 },
      new Blob(["%PDF"]), "FIR.pdf", f as unknown as typeof fetch, () => COOKIES);
    expect(r.completa).toBe(true);
    const [url, init] = f.mock.calls[0]! as [string, RequestInit];
    expect(url).toMatch(/\/api\/v1\/evidencias\/leitura\?empresa_id=1$/);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect((init.headers as Record<string, string>)[CABECALHO_CSRF]).toBe("abc=123");
    expect((init.body as FormData).get("arquivo")).toBeInstanceOf(Blob);
  });
});
