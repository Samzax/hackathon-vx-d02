// O boletim e o plano de transição vêm da API em Markdown simples (títulos, listas, negrito).
// Este leitor cobre só isso, sem HTML cru: o texto é sempre texto.

export type Trecho = { tipo: "texto" | "negrito" | "italico" | "codigo"; texto: string };
export type Bloco =
  | { tipo: "titulo"; nivel: number; trechos: Trecho[] }
  | { tipo: "lista"; itens: { nivel: number; trechos: Trecho[] }[] }
  | { tipo: "paragrafo"; trechos: Trecho[] };

export function trechos(linha: string): Trecho[] {
  const out: Trecho[] = [];
  const re = /\*\*(.+?)\*\*|`([^`]+)`|(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])/g;
  let ultimo = 0;
  for (let m = re.exec(linha); m; m = re.exec(linha)) {
    if (m.index > ultimo) out.push({ tipo: "texto", texto: linha.slice(ultimo, m.index) });
    if (m[1] !== undefined) out.push({ tipo: "negrito", texto: m[1] });
    else if (m[2] !== undefined) out.push({ tipo: "codigo", texto: m[2] });
    else out.push({ tipo: "italico", texto: m[3]! });
    ultimo = m.index + m[0].length;
  }
  if (ultimo < linha.length) out.push({ tipo: "texto", texto: linha.slice(ultimo) });
  return out;
}

export function lerMarkdown(md: string): Bloco[] {
  const blocos: Bloco[] = [];
  let paragrafo: string[] = [];
  const fechar = () => {
    if (paragrafo.length) blocos.push({ tipo: "paragrafo", trechos: trechos(paragrafo.join(" ")) });
    paragrafo = [];
  };
  for (const bruta of md.replace(/\r\n/g, "\n").split("\n")) {
    const linha = bruta.trimEnd();
    const titulo = /^(#{1,6})\s+(.*)$/.exec(linha);
    const item = /^(\s*)[-*]\s+(.*)$/.exec(linha);
    if (!linha.trim()) {
      fechar();
    } else if (titulo) {
      fechar();
      blocos.push({ tipo: "titulo", nivel: titulo[1]!.length, trechos: trechos(titulo[2]!) });
    } else if (item) {
      fechar();
      const nivel = Math.floor(item[1]!.replace(/\t/g, "  ").length / 2);
      const ultimo = blocos.at(-1);
      const novo = { nivel, trechos: trechos(item[2]!) };
      if (ultimo?.tipo === "lista") ultimo.itens.push(novo);
      else blocos.push({ tipo: "lista", itens: [novo] });
    } else if (/^\s{2,}\S/.test(linha) && blocos.at(-1)?.tipo === "lista" && !paragrafo.length) {
      // continuação de um item ("  - antes: ..." já é item; texto solto recuado junta no anterior)
      const lista = blocos.at(-1) as Extract<Bloco, { tipo: "lista" }>;
      lista.itens.at(-1)!.trechos.push({ tipo: "texto", texto: " " }, ...trechos(linha.trim()));
    } else {
      paragrafo.push(linha.trim());
    }
  }
  fechar();
  return blocos;
}
