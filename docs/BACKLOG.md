# Backlog de trabalho autônomo (noite de 5 para 6/11/2026)

Autorizado pelo usuário: seguir sozinho com o escopo combinado (torre com Hoje / Transição /
Mudanças, Res. 95 + Res. 220 + NRs + licença fictícia), fazendo commit e push no repositório
privado, sem linhas de coautoria. Nada fora do repositório (sem mensagens, compras, contas).

Regras: rodar `uv run pytest` antes de cada commit; IA só com DeepSeek V4.1 Flash (OpenCode Go)
ou Haiku/Sonnet; nada de Opus; chaves só no `.env`; o CSV bruto do SIGBM (tem CPF) nunca vai pro Git.

## Fila (marcar [x] ao terminar)

- [x] Curadoria da Res. 95/2022 -> `curadoria/res95_2022.csv` -> `cadastro/res95_2022.csv`
      (códigos R95-01..; ver `data/historico_serra_azul.json`, que já usa R95-01, -02, -05, -06, -09, -16;
      vigência 2022-02-07 a 2027-08-01; incluir obrigações de emergência/PAEBM dos arts. 23-45)
- [x] Curadoria da NR-13 -> `cadastro/nr13.csv` (tipo equipamento; N13-03 = exame externo periódico,
      N13-04 = exame interno periódico, conforme a Tabela 2 e a categoria do vaso; conferir no texto)
- [x] Testes da torre (`tests/test_torre.py`): B3 com FIR atrasada, B4 com dado faltando,
      L1 com renovação vencendo, transição 95 -> 220, Res. 245 pendente só na B2
- [x] Teste de fumaça da interface com `streamlit.testing.v1.AppTest`
- [x] Revisar a interface rodando de verdade (preview) e corrigir o que estiver feio ou confuso
- [x] Transição: mostrar as obrigações equivalentes (ex.: RPSB na 95 e na 220) em vez de só "sai/entra"
- [x] Mudanças: ao aprovar a Res. 245, a OB-01 da B2 sai da transição de 2027 e vai para 2029
- [x] NR-22 Portaria MTE 105/2026: não serve como mudança pendente (é de jan/2026, já no texto da NR-22),
      mas mostra MTE e ANM com a mesma data para a ZAS (26/12/2029): virou cadastro N22-ZAS1/2 e linha do tempo
- [x] Leitor de evidência (FIR em PDF -> período e campos): regra + IA conferida, gatilho de ISE, envio na aba Hoje
- [x] Atualizar README e docs/ARQUITETURA.md com a torre, agenda, curadoria e custos medidos
