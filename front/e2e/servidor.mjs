// Sobe a API de verdade (uvicorn) para os testes de ponta a ponta: banco SQLite novo a cada rodada,
// e a própria API servindo o front exportado (front/out) na mesma origem, como em produção.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
const raiz = resolve(aqui, "..", "..");
const dados = join(aqui, ".dados");
const porta = process.env.PORTA_E2E ?? "8765";

if (!existsSync(join(raiz, "front", "out", "index.html"))) {
  console.error("front/out não existe: rode `npm run build` antes dos testes de ponta a ponta.");
  process.exit(1);
}
rmSync(dados, { recursive: true, force: true });
mkdirSync(dados, { recursive: true });

const api = spawn("uv", ["run", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", porta], {
  cwd: raiz,
  stdio: "inherit",
  env: {
    ...process.env,
    REGULAIA_DATABASE_URL: join(dados, "e2e.db"),
    REGULAIA_CACHE_URL: join(dados, "cache.db"),
    REGULAIA_ARMAZENAMENTO: join(dados, "uploads"),
    REGULAIA_FRONT: join(raiz, "front", "out"),
    REGULAIA_MONTAR_DEMO: "1",
  },
});

const parar = () => api.kill();
process.on("SIGINT", parar);
process.on("SIGTERM", parar);
process.on("exit", parar);
api.on("exit", (codigo) => process.exit(codigo ?? 0));
