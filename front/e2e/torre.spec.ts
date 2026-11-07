import { expect, type Page, test } from "@playwright/test";

// Cada teste entra na demo e volta a demo ao estado inicial: a ordem dos testes não importa.
async function entrarNaDemo(page: Page) {
  await page.goto("/entrar/");
  await page.getByRole("button", { name: "Entrar na demo" }).click();
  await page.waitForURL(/\/caixa\/$/);
  const ok = await page.evaluate(async () => {
    const csrf = decodeURIComponent(document.cookie.match(/(?:^|; )mitra_csrf=([^;]*)/)?.[1] ?? "");
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
  await expect(cartao).toContainText("Quem decide esta mudança: curadoria Mitra");
  await expect(cartao.getByRole("button", { name: "Aprovar" })).toHaveCount(0);

  await verComo(page, "Curadoria Mitra (plataforma)");
  await expect(cartao.getByRole("button", { name: "Aprovar", exact: true })).toBeVisible();
  await cartao.getByRole("button", { name: "Aprovar", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "OB-01: mudança aprovada" })).toBeVisible();
  await expect(page.getByText("Nenhuma mudança aguardando decisão")).toBeVisible();
  await expect(page.getByTestId("decisoes")).toContainText("OB-01");
  await expect(page.getByTestId("decisoes")).toContainText("aprovada");

  await verComo(page, "Diretoria (todos os ativos)");
  await expect(page.getByTestId("decisoes")).toContainText("Resolução ANM nº 245");
});

test("a curadoria da plataforma só lê os dados da empresa", async ({ page }) => {
  await entrarNaDemo(page);
  await expect(page.getByTestId("so-leitura")).toHaveCount(0);
  await verComo(page, "Curadoria Mitra (plataforma)");
  await expect(page.getByTestId("so-leitura")).toHaveText("visão da plataforma: só leitura");

  // vê as mesmas 4 atrasadas, sem o botão de registrar
  const atrasadas = page.getByTestId("grupo-atrasada");
  await expect(atrasadas.getByTestId("item-caixa")).toHaveCount(4);
  await expect(atrasadas.getByRole("button", { name: "Registrar entrega" })).toHaveCount(0);

  // o cadastro aparece sem campo para editar, e a área do ativo sem o seletor
  await page.goto("/ativos/?id=3&aba=cadastro");
  await expect(page.getByTestId("cadastro")).toContainText("Altura (m)");
  await expect(page.getByTestId("cadastro").locator("input, select")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Salvar no cadastro" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Salvar área" })).toHaveCount(0);

  // nas entregas, a linha abre o histórico, sem registrar, atribuir nem comentar
  await page.goto("/entregas/?status=atrasada");
  await page.getByTestId("tabela-entregas").locator("tbody tr").first().click();
  const uma = page.getByTestId("acoes-uma");
  await expect(uma).toContainText("Histórico");
  await expect(uma.getByRole("button")).toHaveCount(0);
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

// A fila de normas candidatas (data/descoberta_demo.json) fica fora do "Recriar demo": é trabalho da curadoria, não da
// cliente. Por isso só o teste abaixo decide algo nela, e os outros não dependem do que ele aprovou.
const CAUCAO = "Decreto MG 48.747/2023"; // regulamenta a caução da Lei MG 23.291, que está no catálogo

test("curadoria aprova uma norma candidata e a cobertura da Serra Azul muda", async ({ page }) => {
  await page.goto("/entrar/");
  await page.getByLabel("E-mail").fill("curadoria@mitra.demo");
  await page.getByLabel("Senha").fill("serra-azul-2026");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await page.waitForURL(/\/caixa\/$/);
  const nav = page.getByRole("navigation", { name: "Telas da torre" });

  // antes: o decreto espera a curadoria na linha "Barragem · Minas Gerais"
  await nav.getByRole("link", { name: "Cobertura normativa" }).click();
  const mg = page.getByTestId("cobertura-MG-barragem");
  await expect(mg).toHaveAttribute("data-tom", "amarelo");
  await expect(mg.getByTestId("fontes")).toContainText("Assembleia de Minas, 1989–2026, lida em");
  await expect(mg.getByTestId("catalogadas")).toContainText("Lei MG 23.291/2019");
  await expect(mg.getByTestId("em-curadoria")).toContainText(CAUCAO);
  await expect(mg.getByTestId("aprovadas")).toHaveCount(0);

  await nav.getByRole("link", { name: /Normas candidatas/ }).click();
  await page.getByLabel("Jurisdição").selectOption("MG");
  await page.waitForURL(/jurisdicao=MG/);
  await page.getByLabel("Buscar na fila").fill("48.747");
  const cartao = page.getByTestId("norma-candidata").filter({ hasText: CAUCAO });
  await expect(cartao).toHaveCount(1);
  await expect(cartao).toContainText("esperando curadoria");
  await expect(cartao).toContainText("Altera ou regulamenta Lei MG 23.291/2019: conferir se o texto consolidado");
  await expect(cartao.getByTestId("triagem")).toContainText("Confiança 0,96");
  await expect(cartao.getByTestId("leu-texto")).toHaveText("decidiu só pela ementa");
  await expect(cartao.getByRole("link", { name: /Texto oficial/ })).toHaveAttribute("href", /^https:\/\/www\.almg\.gov\.br\//);
  await cartao.getByLabel("Nota da curadoria").fill("extrair a caução do art. 7º");
  await cartao.getByRole("button", { name: "Aprovar" }).click();
  await expect(page.getByRole("status").filter({ hasText: `${CAUCAO}: aprovada, falta extrair` })).toBeVisible();
  await expect(cartao).toHaveCount(0); // saiu das relevantes

  // na fila das aprovadas, com quem decidiu e a nota
  await page.getByLabel("Status").selectOption("aprovada");
  const aprovada = page.getByTestId("norma-candidata").filter({ hasText: CAUCAO });
  await expect(aprovada).toContainText("Aprovada por curadoria@mitra.demo");
  await expect(aprovada).toContainText("extrair a caução do art. 7º");

  // depois: na cobertura da Serra Azul, aprovada, falta extrair
  await nav.getByRole("link", { name: "Cobertura normativa" }).click();
  await expect(mg.getByTestId("aprovadas")).toContainText(CAUCAO);
  await expect(mg.getByTestId("em-curadoria")).not.toContainText(CAUCAO);
});

test("cliente vê a cobertura, não abre a fila da curadoria, e UF sem fonte nunca fica verde", async ({ page }) => {
  await entrarNaDemo(page);
  const nav = page.getByRole("navigation", { name: "Telas da torre" });
  await expect(nav.getByRole("link", { name: /Normas candidatas/ })).toHaveCount(0);
  await page.goto("/regulatorio/normas-candidatas/");
  await page.waitForURL(/\/caixa\/$/);

  // a B4 passa a ficar no Pará: nenhuma fonte automática lê a lei paraense
  const ok = await page.evaluate(async () => {
    const csrf = decodeURIComponent(document.cookie.match(/(?:^|; )mitra_csrf=([^;]*)/)?.[1] ?? "");
    const empresas = await (await fetch("/api/v1/empresas", { credentials: "include" })).json();
    const ativos = await (await fetch(`/api/v1/empresas/${empresas[0].id}/ativos`, { credentials: "include" })).json();
    const b4 = ativos.find((a: { codigo: string }) => a.codigo === "B4");
    const r = await fetch(`/api/v1/ativos/${b4.id}/atributos`, {
      method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ atributos: { uf: "PA" } }),
    });
    return r.ok;
  });
  expect(ok).toBe(true);

  await nav.getByRole("link", { name: "Cobertura normativa" }).click();
  const pa = page.getByTestId("cobertura-PA-barragem");
  await expect(pa).toHaveAttribute("data-tom", "cinza");
  await expect(pa.getByTestId("estado")).toHaveText("sem fonte automática: cobertura não verificada");
  await expect(pa).toContainText("Ativos: B4");
  await expect(pa.getByTestId("fontes")).toContainText("Nenhuma fonte automática para esta jurisdição.");

  // coberta é verde, mas com as lacunas conhecidas ao lado
  const equip = page.getByTestId("cobertura-BR-equipamento");
  await expect(equip).toHaveAttribute("data-tom", "verde");
  await expect(equip.getByTestId("catalogadas")).toContainText("NR-13");
  await expect(equip.getByTestId("lacunas")).toContainText("Normas Regulamentadoras do MTE");
  await expect(page.getByTestId("cobertura-MG-barragem").getByText("Ativos: B1, B2, B3", { exact: true })).toBeVisible();
  await expect(page.getByTestId("cobertura-MG-barragem")).not.toContainText("Abrir na fila da curadoria");
});
