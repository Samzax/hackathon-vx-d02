import { expect, type Page, test } from "@playwright/test";

// Cada teste entra na demo e volta a demo ao estado inicial: a ordem dos testes não importa.
async function entrarNaDemo(page: Page) {
  await page.goto("/entrar/");
  await page.getByRole("button", { name: "Entrar na demo" }).click();
  await page.waitForURL(/\/caixa\/$/);
  const ok = await page.evaluate(async () => {
    const csrf = decodeURIComponent(document.cookie.match(/(?:^|; )regulaia_csrf=([^;]*)/)?.[1] ?? "");
    const r = await fetch("/api/v1/demo/recriar", { method: "POST", credentials: "include", headers: { "X-CSRF-Token": csrf } });
    return r.ok;
  });
  expect(ok).toBe(true);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Caixa de entrada" })).toBeVisible();
}

async function verComo(page: Page, visao: string) {
  await page.getByLabel("Quem está olhando").selectOption(visao);
  await expect(page.getByLabel("Quem está olhando")).toHaveValue(visao);
}

function numero(page: Page, rotulo: string) {
  return page.getByTestId("numeros").getByRole("link", { name: new RegExp(`^${rotulo}`) });
}

test("entrar na demo e ver as 4 atrasadas", async ({ page }) => {
  await entrarNaDemo(page);
  await expect(page.getByTestId("empresa")).toHaveText("Mineradora Serra Azul");
  await expect(page.getByTestId("hoje")).toHaveText("07/11/2026");
  await expect(numero(page, "Atrasada")).toContainText("4");
  const atrasadas = page.getByTestId("grupo-atrasada");
  await expect(atrasadas.getByTestId("item-caixa")).toHaveCount(4);
  await expect(atrasadas).toContainText("Preencher as FIR quinzenalmente");
  await expect(atrasadas).toContainText("Res. ANM 95/2022, art. 19 I");

  // o número leva à lista de entregas já filtrada
  await numero(page, "Atrasada").click();
  await page.waitForURL(/\/entregas\/\?status=atrasada/);
  await expect(page.getByTestId("tabela-entregas").locator("tbody tr")).toHaveCount(4);
});

test("registrar uma entrega tira a obrigação das atrasadas", async ({ page }) => {
  await entrarNaDemo(page);
  const item = page.getByTestId("grupo-atrasada").getByTestId("item-caixa").filter({ hasText: "Preencher as FIR quinzenalmente" });
  await item.getByRole("button", { name: "Registrar entrega" }).click();

  const dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("B3 · Preencher as FIR quinzenalmente");
  await expect(dialogo.getByTestId("periodo-comprovado")).toHaveText("1ª quinzena de outubro/2026");
  await dialogo.getByLabel("Observação").fill("FIR anexada pela consultoria");
  await dialogo.getByRole("button", { name: "Registrar entrega" }).click();

  await expect(page.getByRole("status").filter({ hasText: "Entrega registrada: B3 · R95-01 · 1ª quinzena de outubro/2026" })).toBeVisible();
  await expect(dialogo).toBeHidden();
  await expect(numero(page, "Atrasada")).toContainText("3");
  await expect(page.getByTestId("grupo-atrasada").getByTestId("item-caixa")).toHaveCount(3);

  // a entrega fica no histórico do ativo
  await page.goto("/ativos/?id=3");
  await page.getByRole("tab", { name: "Histórico" }).click();
  await expect(page.getByTestId("ficha")).toContainText("FIR anexada pela consultoria");
});

test("gestor vê só os ativos da área dele", async ({ page }) => {
  await entrarNaDemo(page);
  await verComo(page, "Gerência de Meio Ambiente");
  await expect(numero(page, "Atrasada")).toContainText("1");
  await expect(page.getByTestId("grupo-atrasada")).toContainText("L1 · Monitorar os efluentes");
  await expect(page.getByTestId("grupo-atrasada")).not.toContainText("B3");

  // a Auditoria é da Diretoria, do Regulatório e da TI
  await expect(page.getByRole("navigation", { name: "Telas da torre" }).getByRole("link", { name: "Auditoria" })).toHaveCount(0);

  await page.getByRole("navigation", { name: "Telas da torre" }).getByRole("link", { name: "Ativos" }).click();
  const linhas = page.getByTestId("tabela-ativos").locator("tbody tr");
  await expect(linhas).toHaveCount(1);
  await expect(linhas.first()).toContainText("L1 · Licença de Operação");
  await expect(linhas.first()).toContainText("Gerência de Meio Ambiente");
});

test("curadoria aprova a Res. 245 e a Diretoria vê a decisão", async ({ page }) => {
  await entrarNaDemo(page);
  const nav = page.getByRole("navigation", { name: "Telas da torre" });

  // a norma é pública: a Diretoria da cliente vê a mudança, mas quem decide é a curadoria
  await nav.getByRole("link", { name: /Mudanças/ }).click();
  const cartao = page.getByTestId("mudanca").filter({ hasText: "OB-01" });
  await expect(cartao).toContainText("Resolução ANM nº 245, de 31 de julho de 2026");
  await expect(cartao).toContainText("26/12/2029");
  await expect(cartao).toContainText("Quem decide esta mudança: curadoria RegulaIA");
  await expect(cartao.getByRole("button", { name: "Aprovar" })).toHaveCount(0);

  await verComo(page, "Curadoria RegulaIA (plataforma)");
  await expect(cartao.getByRole("button", { name: "Aprovar", exact: true })).toBeVisible();
  await cartao.getByRole("button", { name: "Aprovar", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "OB-01: mudança aprovada" })).toBeVisible();
  await expect(page.getByText("Nenhuma mudança aguardando decisão")).toBeVisible();
  await expect(page.getByTestId("decisoes")).toContainText("OB-01");
  await expect(page.getByTestId("decisoes")).toContainText("aprovada");

  await verComo(page, "Diretoria (todos os ativos)");
  await expect(page.getByTestId("decisoes")).toContainText("Resolução ANM nº 245");
});

test("TI só administra contas e auditoria", async ({ page }) => {
  await entrarNaDemo(page);
  await verComo(page, "TI (usuários e acessos)");
  await page.waitForURL(/\/usuarios\/$/);
  await expect(page.getByRole("heading", { name: "Usuários e acessos" })).toBeVisible();
  await expect(page.getByTestId("contas")).toContainText("demo@serraazul.demo");
  const nav = page.getByRole("navigation", { name: "Telas da torre" });
  await expect(nav.getByRole("link")).toHaveText(["Usuários e acessos", "Auditoria"]);
  await page.goto("/caixa/");
  await page.waitForURL(/\/usuarios\/$/);
});
