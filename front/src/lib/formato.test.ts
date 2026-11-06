import { describe, expect, it } from "vitest";
import {
  curto, dataBR, diasEntre, emBrasilia, maiuscula, mesAno, mesesAoRedor, nomeDeArquivo, numero, numeroLivre,
  plural, reaisMilhoes, semanasDoMes, somarDias, usd,
} from "./formato";

describe("datas", () => {
  it("ISO vira DD/MM/AAAA e vazio vira travessão", () => {
    expect(dataBR("2026-11-07")).toBe("07/11/2026");
    expect(dataBR("2026-11-07 22:56:38")).toBe("07/11/2026");
    expect(dataBR(null)).toBe("—");
    expect(dataBR("")).toBe("—");
  });

  it("UTC do banco vira horário de Brasília, e a data muda perto da meia-noite", () => {
    expect(emBrasilia("2026-11-05 16:53:43")).toBe("05/11/2026 13:53");
    expect(emBrasilia("2026-11-06 01:10:00")).toBe("05/11/2026 22:10");
    expect(emBrasilia("2026-01-01 02:00:00", false)).toBe("31/12/2025");
    expect(emBrasilia(null)).toBe("—");
  });

  it("conta dias e soma dias sem fuso horário", () => {
    expect(diasEntre("2026-11-07", "2027-08-02")).toBe(268);
    expect(diasEntre("2027-08-02", "2026-11-07")).toBe(-268);
    expect(somarDias("2026-12-30", 3)).toBe("2027-01-02");
    expect(somarDias("2028-02-28", 1)).toBe("2028-02-29");
  });

  it("monta os meses do seletor e as semanas do calendário (segunda primeiro)", () => {
    expect(mesesAoRedor("2026-11-07", 1, 2)).toEqual(["2026-10-01", "2026-11-01", "2026-12-01", "2027-01-01"]);
    const nov = semanasDoMes(2026, 11); // 1/11/2026 é domingo
    expect(nov[0]).toEqual([0, 0, 0, 0, 0, 0, 1]);
    expect(nov.flat().filter(Boolean)).toHaveLength(30);
    expect(nov.every((s) => s.length === 7)).toBe(true);
    expect(mesAno("2027-08-02")).toBe("ago/2027");
  });
});

describe("números", () => {
  it("formato brasileiro", () => {
    expect(numero(7884)).toBe("7.884");
    expect(numero(1234.5, 1)).toBe("1.234,5");
    expect(numeroLivre(68)).toBe("68");
    expect(numeroLivre(9771474.42)).toBe("9.771.474,42");
  });

  it("dólar com vírgula e reais em milhões", () => {
    expect(usd(0.00231645)).toBe("US$ 0,0023");
    expect(usd(0.1560067, 3)).toBe("US$ 0,156");
    expect(reaisMilhoes(461 * 2250 * 12)).toBe("R$ 12,4 mi");
  });

  it("plural pelo número", () => {
    expect(plural(1, "obrigação", "obrigações")).toBe("1 obrigação");
    expect(plural(0, "obrigação", "obrigações")).toBe("0 obrigações");
    expect(plural(1200, "ato", "atos")).toBe("1.200 atos");
  });
});

describe("texto", () => {
  it("corta no limite de palavra", () => {
    expect(curto("Preencher as FIR quinzenalmente", 100)).toBe("Preencher as FIR quinzenalmente");
    expect(curto("Preencher o EIR no SIGBM até o fim da quinzena", 20)).toBe("Preencher o EIR no…");
  });

  it("maiúscula na primeira letra e nome de arquivo sem acento", () => {
    expect(maiuscula("falta a data")).toBe("Falta a data");
    expect(maiuscula("")).toBe("");
    expect(nomeDeArquivo("Gerência de Geotecnia")).toBe("Gerencia_de_Geotecnia");
  });
});
