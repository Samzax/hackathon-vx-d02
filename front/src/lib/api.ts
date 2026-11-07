// Cliente da API: tipado pelo contrato (api/openapi.json -> api-tipos.ts), sempre com o cookie de
// sessão (credentials: "include") e, em toda escrita, o cabeçalho X-CSRF-Token com o valor do
// cookie mitra_csrf (double submit). O front não fala com mais nada além desta API.
import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./api-tipos";

export type Esquemas = components["schemas"];

export const COOKIE_CSRF = "mitra_csrf";
export const CABECALHO_CSRF = "X-CSRF-Token";
const ESCRITA = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Em produção a API serve o front na mesma origem (""); no `next dev`, a API fica na 8000. */
export const BASE_API =
  process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

export function lerCookie(nome: string, cookies: string): string | null {
  for (const parte of cookies.split(";")) {
    const [k, ...v] = parte.trim().split("=");
    if (k === nome) return decodeURIComponent(v.join("="));
  }
  return null;
}

function cookiesDoNavegador(): string {
  return typeof document === "undefined" ? "" : document.cookie;
}

/** O middleware que põe o CSRF nas escritas (exportado para o teste). */
export function middlewareCsrf(cookies: () => string = cookiesDoNavegador): Middleware {
  return {
    onRequest({ request }) {
      if (ESCRITA.has(request.method.toUpperCase())) {
        const csrf = lerCookie(COOKIE_CSRF, cookies());
        if (csrf) request.headers.set(CABECALHO_CSRF, csrf);
      }
      return request;
    },
  };
}

export function criarCliente(baseUrl = BASE_API, fetchImpl?: typeof fetch, cookies?: () => string) {
  const c = createClient<paths>({ baseUrl, credentials: "include", ...(fetchImpl ? { fetch: fetchImpl } : {}) });
  c.use(middlewareCsrf(cookies));
  return c;
}

export const api = criarCliente();

/** Erro da API com o status e a mensagem em português que ela devolveu em `detail`. */
export class ErroApi extends Error {
  constructor(public status: number, mensagem: string, public detalhe?: unknown) {
    super(mensagem);
    this.name = "ErroApi";
  }
}

/** O `detail` do FastAPI vira uma frase: texto puro, ou a lista de erros de validação (422). */
export function mensagemDe(detalhe: unknown, status: number): string {
  if (typeof detalhe === "string" && detalhe) return detalhe;
  if (Array.isArray(detalhe) && detalhe.length) {
    return detalhe
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const campo = (d.loc ?? []).filter((x) => x !== "body" && x !== "query").join(".");
        return campo ? `${campo}: ${d.msg ?? "inválido"}` : (d.msg ?? "inválido");
      })
      .join("; ");
  }
  if (status === 401) return "entre na torre para continuar";
  if (status === 403) return "sem permissão para isto";
  if (status === 404) return "não encontrado";
  if (status >= 500) return "a API não respondeu como esperado; tente de novo";
  return `erro ${status}`;
}

type Resposta<T> = { data?: T; error?: unknown; response: Response };

/** Desembrulha a resposta do openapi-fetch: devolve o dado ou lança ErroApi. */
export async function dados<T>(p: Promise<Resposta<T>>): Promise<T> {
  let r: Resposta<T>;
  try {
    r = await p;
  } catch {
    throw new ErroApi(0, "sem conexão com a API: confira se ela está no ar");
  }
  if (r.error !== undefined || !r.response.ok) {
    const detalhe = (r.error as { detail?: unknown } | undefined)?.detail;
    throw new ErroApi(r.response.status, mensagemDe(detalhe, r.response.status), r.error);
  }
  return r.data as T;
}

export type Consulta = Record<string, string | number | boolean | null | undefined | (string | number)[]>;

/** URL de uma rota da API com a consulta (listas viram parâmetros repetidos, como o FastAPI espera). */
export function urlDe(caminho: string, consulta: Consulta = {}, base = BASE_API): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(consulta)) {
    if (v === null || v === undefined || v === "") continue;
    for (const x of Array.isArray(v) ? v : [v]) qs.append(k, String(x));
  }
  const q = qs.toString();
  return `${base}${caminho}${q ? `?${q}` : ""}`;
}

/** Texto de uma rota que não devolve JSON (boletim em Markdown, plano de transição). */
export async function texto(caminho: string, consulta: Consulta = {}, fetchImpl: typeof fetch = fetch): Promise<string> {
  const r = await fetchImpl(urlDe(caminho, consulta), { credentials: "include" });
  if (!r.ok) throw new ErroApi(r.status, mensagemDe(await detalheDe(r), r.status));
  return r.text();
}

async function detalheDe(r: Response): Promise<unknown> {
  try {
    return ((await r.json()) as { detail?: unknown }).detail;
  } catch {
    return undefined;
  }
}

/** Baixa um arquivo da API (PDF, .md, .ics, .xlsx) com o nome escolhido. Nada é enviado a ninguém. */
export async function baixar(caminho: string, consulta: Consulta, nome: string): Promise<void> {
  const r = await fetch(urlDe(caminho, consulta), { credentials: "include" });
  if (!r.ok) throw new ErroApi(r.status, mensagemDe(await detalheDe(r), r.status));
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Envia um arquivo (multipart) para a API, com o CSRF. Usado no leitor de evidência e no comprovante. */
export async function enviarArquivo<T>(caminho: string, consulta: Consulta, arquivo: File | Blob, nome?: string,
  fetchImpl: typeof fetch = fetch, cookies: () => string = cookiesDoNavegador): Promise<T> {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo, nome ?? (arquivo instanceof File ? arquivo.name : "documento.pdf"));
  const csrf = lerCookie(COOKIE_CSRF, cookies());
  let r: Response;
  try {
    r = await fetchImpl(urlDe(caminho, consulta), {
      method: "POST", body: corpo, credentials: "include", headers: csrf ? { [CABECALHO_CSRF]: csrf } : {},
    });
  } catch {
    throw new ErroApi(0, "sem conexão com a API: confira se ela está no ar");
  }
  if (!r.ok) throw new ErroApi(r.status, mensagemDe(await detalheDe(r), r.status));
  return (await r.json()) as T;
}
