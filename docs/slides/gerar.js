// Gera os slides do pitch (docs/PITCH.md) em .pptx, para subir ao Google Slides.
// As notas do apresentador saem das falas do PITCH.md; o que vai na tela está aqui.
// Uso: npm install pptxgenjs@3.12.0 (fora do repositório) e
//      NODE_PATH=<pasta>/node_modules node docs/slides/gerar.js saida.pptx
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const saida = process.argv[2] || "Mitra_pitch.pptx";
const pitch = fs.readFileSync(path.join(__dirname, "..", "PITCH.md"), "utf-8");

// ---------- notas: falas e narração de cada seção "## N · Título (tempo)" ----------
function notas() {
  const partes = pitch.split(/^## /m).slice(1);
  const porSlide = {};
  for (const p of partes) {
    const m = p.match(/^(\d+) · (.+?) \((.+?)\)/);
    if (!m) continue;
    const linhas = [`${m[2]} (${m[3]})`, ""];
    for (const l of p.split("\n")) {
      const fala = l.match(/\*\*(?:Fala|Narração):\*\* "([^"]+)"/);
      if (!fala) continue;
      const corte = l.match(/^- \*\*(\d:\d\d [^*]+?)\.\*\*/);
      linhas.push(corte ? `${corte[1]}: ${fala[1]}` : fala[1], "");
    }
    porSlide[m[1]] = linhas.join("\n").trim();
  }
  return porSlide;
}
const NOTAS = notas();

// ---------- tema ----------
const COR = {
  noite: "16212B", tinta: "1E2B36", cinza: "5E6B76", claro: "A9B4BD", linha: "D5DBE0",
  palido: "F2F4F6", ambar: "E3A21A", ambarEscuro: "A86F05", vermelho: "C0392B",
  verde: "2E7D4F", branco: "FFFFFF",
};
const FONTE = "Arial";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5,625 pol.
pres.title = "Mitra: pitch";
pres.author = "Time Mitra";
pres.theme = { headFontFace: FONTE, bodyFontFace: FONTE };

pres.defineSlideMaster({
  title: "CONTEUDO",
  background: { color: COR.branco },
  objects: [
    { text: { text: "Mitra · Hackathon VX 2026",
              options: { x: 0.5, y: 5.2, w: 4, h: 0.3, fontFace: FONTE, fontSize: 9, color: COR.cinza, margin: 0 } } },
    { placeholder: { options: { name: "titulo", type: "title", x: 0.5, y: 0.35, w: 9, h: 0.7, fontFace: FONTE,
                                fontSize: 28, bold: true, color: COR.tinta, margin: 0, valign: "middle", align: "left" },
                     text: "" } },
  ],
  slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.3, fontFace: FONTE, fontSize: 9, color: COR.cinza, align: "right" },
});
pres.defineSlideMaster({ title: "ESCURO", background: { color: COR.noite } });

function slideConteudo(titulo, n) {
  const s = pres.addSlide({ masterName: "CONTEUDO" });
  s.addText(titulo, { placeholder: "titulo" });
  if (NOTAS[n]) s.addNotes(NOTAS[n]);
  return s;
}
function texto(s, t, o) { s.addText(t, { isTextBox: true, fontFace: FONTE, margin: 0, ...o }); }
function caixa(s, o) { s.addShape(pres.shapes.ROUNDED_RECTANGLE, { rectRadius: 0.08, line: { type: "none" }, ...o }); }

// ---------- 1 · Metade já foi embargada ----------
{
  const s = pres.addSlide({ masterName: "ESCURO" });
  texto(s, "Mitra", { x: 0.5, y: 0.4, w: 3, h: 0.35, fontSize: 14, bold: true, color: COR.ambar });
  texto(s, [
    { text: "223", options: { color: COR.ambar } },
    { text: " de 461", options: { color: COR.branco } },
  ], { x: 0.5, y: 0.95, w: 9, h: 1.6, fontSize: 96, bold: true, valign: "middle" });
  texto(s, "barragens de mineração na Política Nacional de Segurança de Barragens já foram embargadas",
        { x: 0.5, y: 2.6, w: 8.2, h: 0.75, fontSize: 20, color: COR.branco, valign: "top" });
  texto(s, "Fonte: SIGBM, 05/11/2026", { x: 0.5, y: 3.4, w: 6, h: 0.3, fontSize: 11, color: COR.claro });
  const stats = [["76", "embargadas hoje (SIGBM)"], ["85", "autos de embargo em 2025 (ANM)"]];
  stats.forEach(([n, rotulo], i) => {
    const x = 0.5 + i * 4.3;
    texto(s, n, { x, y: 4.05, w: 0.9, h: 0.75, fontSize: 36, bold: true, color: COR.ambar, valign: "middle" });
    texto(s, rotulo, { x: x + 0.95, y: 4.05, w: 3.3, h: 0.75, fontSize: 14, color: COR.branco, valign: "middle" });
  });
  s.addNotes(NOTAS["1"]);
}

// ---------- 2 · Sessenta entregas por barragem ----------
{
  const s = slideConteudo("60 entregas por barragem, e a norma muda", "2");
  s.addShape(pres.shapes.OVAL, { x: 1.85, y: 2.2, w: 1.6, h: 1.6, fill: { color: COR.noite }, line: { type: "none" } });
  texto(s, [
    { text: "~60", options: { fontSize: 30, bold: true, color: COR.ambar, breakLine: true } },
    { text: "entregas por ano", options: { fontSize: 11, color: COR.branco } },
  ], { x: 1.85, y: 2.2, w: 1.6, h: 1.6, align: "center", valign: "middle" });
  const entregas = [["FIR", "quinzenal"], ["Extrato", "quinzenal"], ["Simulado", "anual"],
                    ["DCE", "semestral"], ["RISR", "semestral"], ["Treinamento", "semestral"]];
  entregas.forEach(([nome, freq], i) => {
    const x = i < 3 ? 0.5 : 3.6, y = 1.55 + (i % 3) * 0.95;
    caixa(s, { x, y, w: 1.2, h: 0.62, fill: { color: COR.palido } });
    texto(s, [
      { text: nome, options: { bold: true, fontSize: 12, color: COR.tinta, breakLine: true } },
      { text: freq, options: { fontSize: 10, color: COR.cinza } },
    ], { x, y, w: 1.2, h: 0.62, align: "center", valign: "middle" });
  });
  texto(s, "Res. ANM 95/2022, por barragem", { x: 0.5, y: 4.5, w: 4.3, h: 0.3, fontSize: 10, color: COR.cinza });

  const datas = [
    ["Notícia no site da ANM", "31/12/2029", COR.vermelho, "data errada", true],
    ["Resolução ANM 245/2026, no Diário Oficial", "26/12/2029", COR.verde, "é a que vale", false],
  ];
  datas.forEach(([fonte, data, cor, nota, riscado], i) => {
    const y = 1.35 + i * 1.5;
    caixa(s, { x: 5.4, y, w: 4.1, h: 1.3, fill: { color: COR.palido } });
    texto(s, fonte, { x: 5.65, y: y + 0.15, w: 3.7, h: 0.3, fontSize: 12, color: COR.cinza });
    texto(s, data, { x: 5.65, y: y + 0.5, w: 2.4, h: 0.6, fontSize: 30, bold: true, color: cor,
                     strike: riscado ? "sngStrike" : undefined, valign: "middle" });
    texto(s, nota, { x: 8.0, y: y + 0.5, w: 1.35, h: 0.6, fontSize: 13, bold: true, color: cor, valign: "middle" });
  });
  texto(s, "A ANM tem 53 servidores para fiscalizar cerca de 900 barragens (ASANM).",
        { x: 5.4, y: 4.4, w: 4.1, h: 0.5, fontSize: 12, color: COR.tinta });
}

// ---------- 3 · Por que agora ----------
{
  const s = slideConteudo("Por que agora", "3");
  texto(s, "268 dias", { x: 0.5, y: 1.3, w: 4.6, h: 1.1, fontSize: 60, bold: true, color: COR.ambarEscuro, valign: "middle" });
  texto(s, "de 07/11/2026 até 02/08/2027, quando a Res. 220 substitui a Res. 95",
        { x: 0.5, y: 2.45, w: 4.4, h: 0.6, fontSize: 14, color: COR.tinta });
  [["Res. 95", COR.palido, COR.tinta], ["Res. 220", COR.noite, COR.branco]].forEach(([t, fundo, cor], i) => {
    const x = 0.5 + i * 2.35;
    caixa(s, { x, y: 3.35, w: 1.75, h: 0.7, fill: { color: fundo } });
    texto(s, t, { x, y: 3.35, w: 1.75, h: 0.7, fontSize: 18, bold: true, color: cor, align: "center", valign: "middle" });
  });
  texto(s, "→", { x: 2.25, y: 3.35, w: 0.6, h: 0.7, fontSize: 26, bold: true, color: COR.cinza, align: "center", valign: "middle" });
  texto(s, "E a 220 já mudou antes de valer (Res. 245/2026).", { x: 0.5, y: 4.3, w: 4.4, h: 0.4, fontSize: 12, color: COR.cinza });

  const linhas = [["126", "empresas com barragem na Política Nacional"],
                  ["461", "barragens vão refazer o mapa de obrigações"],
                  ["77", "dessas barragens estão em alerta ou emergência hoje"]];
  linhas.forEach(([n, t], i) => {
    const y = 1.35 + i * 1.12;
    caixa(s, { x: 5.4, y, w: 4.1, h: 0.95, fill: { color: COR.palido } });
    texto(s, n, { x: 5.6, y, w: 1.2, h: 0.95, fontSize: 30, bold: true, color: COR.tinta, valign: "middle" });
    texto(s, t, { x: 6.85, y, w: 2.5, h: 0.95, fontSize: 13, color: COR.tinta, valign: "middle" });
  });
  texto(s, "Fonte: SIGBM, 05/11/2026", { x: 5.4, y: 4.75, w: 4.1, h: 0.3, fontSize: 10, color: COR.cinza });
}

// ---------- 4 · A torre em uma frase ----------
{
  const s = slideConteudo("A torre em uma frase", "4");
  const entradas = [["De cima", "Diário Oficial → obrigação", 1.35], ["De baixo", "PDF da operação → baixa ou alerta", 3.55]];
  entradas.forEach(([rot, t, y]) => {
    caixa(s, { x: 0.5, y, w: 3.5, h: 1.05, fill: { color: COR.palido } });
    texto(s, [
      { text: rot, options: { fontSize: 11, color: COR.cinza, breakLine: true } },
      { text: t, options: { fontSize: 15, bold: true, color: COR.tinta } },
    ], { x: 0.7, y, w: 3.2, h: 1.05, valign: "middle" });
  });
  s.addShape(pres.shapes.LINE, { x: 4.0, y: 1.875, w: 1.95, h: 0.75, line: { color: COR.cinza, width: 2, endArrowType: "triangle" } });
  s.addShape(pres.shapes.LINE, { x: 4.0, y: 3.325, w: 1.95, h: 0.75, flipV: true,
                                 line: { color: COR.cinza, width: 2, endArrowType: "triangle" } });
  caixa(s, { x: 4.2, y: 2.03, w: 1.55, h: 0.42, fill: { color: COR.ambar } });
  texto(s, "pessoa aprova", { x: 4.2, y: 2.03, w: 1.55, h: 0.42, fontSize: 12, bold: true, color: COR.noite,
                                  align: "center", valign: "middle" });
  caixa(s, { x: 5.95, y: 2.1, w: 3.55, h: 1.75, fill: { color: COR.noite } });
  texto(s, [
    { text: "Cada ativo", options: { fontSize: 20, bold: true, color: COR.branco, breakLine: true } },
    { text: "barragem, vaso de pressão, licença", options: { fontSize: 12, color: COR.claro, breakLine: true } },
    { text: "o que vence, de quem é, se já foi entregue", options: { fontSize: 12, color: COR.ambar } },
  ], { x: 6.2, y: 2.1, w: 3.2, h: 1.75, valign: "middle", paraSpaceAfter: 4 });
  texto(s, "Nada muda sem uma pessoa aprovar.", { x: 5.95, y: 4.1, w: 3.55, h: 0.4, fontSize: 13, color: COR.cinza });
}

// ---------- 5 · Vídeo da demo ----------
{
  const s = pres.addSlide({ masterName: "ESCURO" });
  texto(s, "Demo", { x: 0.5, y: 0.3, w: 4, h: 0.45, fontSize: 18, bold: true, color: COR.ambar });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 0.85, w: 9, h: 4.4, fill: { color: "0E161D" },
                                      line: { color: COR.cinza, width: 1, dashType: "dash" } });
  texto(s, [
    { text: "Inserir aqui o vídeo da demo", options: { fontSize: 20, bold: true, color: COR.branco, breakLine: true } },
    { text: "Inserir → Vídeo → Google Drive, e apagar esta caixa. Narração ao vivo nas notas.",
      options: { fontSize: 12, color: COR.claro } },
  ], { x: 0.5, y: 0.85, w: 9, h: 4.4, align: "center", valign: "middle" });
  s.addNotes(NOTAS["5"]);
}

// ---------- 6 · Por que dá para confiar ----------
{
  const s = slideConteudo("Por que dá para confiar", "6");
  const numeros = [["99,97%", "do Diário Oficial nunca chega à IA: regra antes de IA"],
                   ["US$ 0,065", "para cadastrar a Res. 95 inteira com IA"],
                   ["66", "trechos do cadastro conferidos contra o texto oficial"],
                   ["170+", "testes automáticos; a demo roda sem internet"]];
  numeros.forEach(([n, t], i) => {
    const x = 0.5 + i * 2.3;
    caixa(s, { x, y: 1.35, w: 2.05, h: 2.1, fill: { color: COR.palido } });
    texto(s, n, { x: x + 0.15, y: 1.5, w: 1.8, h: 0.8, fontSize: 24, bold: true, color: COR.tinta, valign: "middle" });
    texto(s, t, { x: x + 0.15, y: 2.35, w: 1.8, h: 0.95, fontSize: 12, color: COR.cinza, valign: "top" });
  });
  const passos = ["IA propõe", "Python confere trecho e data no ato", "pessoa aprova"];
  const larg = [1.6, 3.4, 1.6];
  let x = 0.5;
  passos.forEach((p, i) => {
    caixa(s, { x, y: 3.85, w: larg[i], h: 0.6, fill: { color: i === 2 ? COR.ambar : COR.noite } });
    texto(s, p, { x, y: 3.85, w: larg[i], h: 0.6, fontSize: 13, bold: true, color: i === 2 ? COR.noite : COR.branco,
                  align: "center", valign: "middle" });
    x += larg[i];
    if (i < 2) {
      texto(s, "→", { x, y: 3.85, w: 0.55, h: 0.6, fontSize: 20, bold: true, color: COR.cinza, align: "center", valign: "middle" });
      x += 0.55;
    }
  });
}

// ---------- 7 · Mercado e modelo ----------
{
  const s = slideConteudo("Mercado e modelo", "7");
  const funil = [[908, 2.6, "barragens de mineração cadastradas", "TAM: R$ 24,5 mi por ano"],
                 [461, 2.1, "na Política Nacional (PNSB)", "SAM: R$ 12,4 mi por ano"],
                 [208, 1.6, "dos 59 grupos com 2 a 9 barragens", "entrada: R$ 5,6 mi por ano"],
                 [46, 1.1, "meta em 3 anos: 10% da PNSB, ~13 grupos", "SOM: R$ 1,2 mi por ano"]];
  funil.forEach(([n, w, rot, rec], i) => {
    const y = 1.2 + i * 0.7;
    caixa(s, { x: 0.5, y, w, h: 0.58, fill: { color: i === 3 ? COR.ambar : COR.noite } });
    texto(s, String(n), { x: 0.65, y, w: w - 0.2, h: 0.58, fontSize: 20, bold: true,
                          color: i === 3 ? COR.noite : COR.branco, valign: "middle" });
    texto(s, [
      { text: rot, options: { fontSize: 11, color: COR.cinza, breakLine: true } },
      { text: rec, options: { fontSize: 13, bold: true, color: COR.tinta } },
    ], { x: 0.5 + w + 0.15, y, w: 6.05 - (0.5 + w + 0.15), h: 0.58, valign: "middle" });
  });

  // a escada: o SAM é a porta de entrada, não o tamanho do negócio
  texto(s, "Mesmo motor, outro cadastro", { x: 0.5, y: 4.02, w: 9, h: 0.28, fontSize: 12, bold: true, color: COR.tinta });
  const escada = [["461 barragens da PNSB", "a porta de entrada"],
                  ["8.086 mineradoras", "a mineradora inteira: NR-13, NR-22, licença (já na demo)"],
                  ["29.761 barragens do país", "água, energia e resíduos (SNISB)"]];
  escada.forEach(([n, d], i) => {
    const x = 0.5 + i * 3.1;
    caixa(s, { x, y: 4.32, w: 2.8, h: 0.55, fill: { color: i === 0 ? COR.palido : COR.branco }, line: { color: COR.cinza, width: 0.5 } });
    texto(s, [
      { text: n, options: { fontSize: 12, bold: true, color: COR.tinta, breakLine: true } },
      { text: d, options: { fontSize: 9, color: COR.cinza } },
    ], { x: x + 0.1, y: 4.32, w: 2.65, h: 0.55, valign: "middle" });
    if (i < 2) texto(s, "→", { x: x + 2.8, y: 4.32, w: 0.3, h: 0.55, fontSize: 16, bold: true, color: COR.cinza, align: "center", valign: "middle" });
  });

  caixa(s, { x: 6.3, y: 1.2, w: 3.2, h: 2.68, fill: { color: COR.palido } });
  texto(s, "Como ganha dinheiro", { x: 6.5, y: 1.3, w: 3.2, h: 0.4, fontSize: 15, bold: true, color: COR.tinta });
  const modelo = [["Assinatura por ativo", "R$ 1.500 por barragem por mês + R$ 150 por outro ativo"],
                  ["Implantação", "valor único: SIGBM, normas, responsáveis"],
                  ["Licença para consultoria", "que também é canal de venda"]];
  modelo.forEach(([t, d], i) => {
    texto(s, [
      { text: t, options: { fontSize: 13, bold: true, color: COR.tinta, breakLine: true } },
      { text: d, options: { fontSize: 11, color: COR.cinza } },
    ], { x: 6.5, y: 1.75 + i * 0.7, w: 2.9, h: 0.66, valign: "top" });
  });
  texto(s, "Preço a validar com 10 entrevistas e 3 pilotos pagos. Barragens: SIGBM, 05/11/2026; SNISB: ANA, RSB 2026; CFEM: ANM, 2025.",
        { x: 0.5, y: 4.92, w: 8.4, h: 0.28, fontSize: 10, italic: true, color: COR.cinza });
}

// ---------- 8 · Concorrência ----------
{
  const s = slideConteudo("Concorrência", "8");
  caixa(s, { x: 0.5, y: 1.35, w: 4.3, h: 2.75, fill: { color: COR.palido } });
  texto(s, [
    { text: "Monitoramento legal", options: { fontSize: 16, bold: true, color: COR.tinta, breakLine: true } },
    { text: "Sigalei, Verde Ghaia, Ius Natura", options: { fontSize: 12, color: COR.cinza } },
  ], { x: 0.75, y: 1.55, w: 3.8, h: 0.8, valign: "top" });
  texto(s, "“O que mudou na lei?”", { x: 0.75, y: 2.5, w: 3.8, h: 1.2, fontSize: 24, bold: true, color: COR.cinza, valign: "middle" });

  caixa(s, { x: 5.2, y: 1.35, w: 4.3, h: 2.75, fill: { color: COR.noite } });
  texto(s, [
    { text: "Mitra", options: { fontSize: 16, bold: true, color: COR.ambar, breakLine: true } },
    { text: "por ativo, lendo o documento que comprova", options: { fontSize: 12, color: COR.claro } },
  ], { x: 5.45, y: 1.55, w: 3.8, h: 0.8, valign: "top" });
  texto(s, "“O que esta barragem precisa entregar, até quando, e já entregou?”",
        { x: 5.45, y: 2.4, w: 3.8, h: 1.5, fontSize: 19, bold: true, color: COR.branco, valign: "middle" });
  texto(s, "As consultorias que fazem a declaração de estabilidade não são concorrentes: são o nosso canal.",
        { x: 0.5, y: 4.4, w: 9, h: 0.45, fontSize: 13, color: COR.tinta });
}

// ---------- 9 · Próximos passos ----------
{
  const s = slideConteudo("Próximos passos", "9");
  s.addShape(pres.shapes.LINE, { x: 1.55, y: 1.9, w: 6.9, h: 0, line: { color: COR.linha, width: 3 } });
  const marcos = [["Hoje", "nov/2026: demo pronta"], ["Pilotos", "3 pilotos pagos em MG e 1 consultoria parceira"],
                  ["Preço validado", "10 entrevistas com geotecnia e compliance"], ["02/08/2027", "Res. 220 entra em vigor"]];
  marcos.forEach(([t, d], i) => {
    const cx = 1.55 + i * (6.9 / 3);
    s.addShape(pres.shapes.OVAL, { x: cx - 0.14, y: 1.76, w: 0.28, h: 0.28,
                                   fill: { color: i === 3 ? COR.ambar : COR.noite }, line: { type: "none" } });
    texto(s, [
      { text: t, options: { fontSize: 14, bold: true, color: COR.tinta, breakLine: true } },
      { text: d, options: { fontSize: 11, color: COR.cinza } },
    ], { x: cx - 1.05, y: 2.2, w: 2.1, h: 0.95, align: "center", valign: "top" });
  });
  texto(s, "Depois: barragens de água e energia, e as normas de toda a mineradora, no mesmo motor.",
        { x: 0.5, y: 3.45, w: 9, h: 0.4, fontSize: 13, color: COR.tinta });
  caixa(s, { x: 0.5, y: 4.05, w: 9, h: 0.8, fill: { color: COR.palido } });
  texto(s, [
    { text: "Time", options: { fontSize: 11, bold: true, color: COR.cinza, breakLine: true } },
    { text: "Daniel Couto · Larissa Albuquerque · Monique Cardoso · Rildo Parasio · Samuel Araujo",
      options: { fontSize: 14, color: COR.tinta } },
  ], { x: 0.75, y: 4.05, w: 8.5, h: 0.8, valign: "middle" });
}

// ---------- 10 · Fechamento ----------
{
  const s = pres.addSlide({ masterName: "ESCURO" });
  texto(s, "A norma muda, a torre muda junto, e uma pessoa decide.",
        { x: 0.5, y: 1.4, w: 9, h: 1.6, fontSize: 34, bold: true, color: COR.branco, valign: "middle" });
  texto(s, "Mitra", { x: 0.5, y: 3.3, w: 4, h: 0.5, fontSize: 22, bold: true, color: COR.ambar });
  texto(s, "Hackathon VX · Desafio 02 · Mineradora Serra Azul é fictícia",
        { x: 0.5, y: 3.85, w: 8, h: 0.35, fontSize: 12, color: COR.claro });
  s.addNotes(NOTAS["10"]);
}

pres.writeFile({ fileName: saida }).then((f) => console.log("gerado:", f));
