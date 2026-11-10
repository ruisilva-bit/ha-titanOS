# Critérios de aceitação e gates restantes

| Critério | Verificação automatizada | Gate físico / ambiente do Rui |
|---|---|---|
| Carrega em HA | Setup/unload/reload em HA 2026.10.1 com mocks | Confirmar versão instalada e arranque sem erros |
| Pairing sem 8009 | Regressão com Cast fechado, PIN válido/inválido | Relato anterior do Rui positivo; não repetir pairing sem necessidade |
| Estado real | Unknown por defeito; evidência explícita; transições e rede separadas | Comparar powerstate com ecrã ligado, standby rápido/prolongado |
| Comandos principais | Método/path/payload Digest e serviços HA; aliases e sequências | Observar efeito de cada tecla; 200 não chega |
| Desligar/WOL | Guard de toggle, concorrência, timeout e magic packet | Autorização prévia + ensaios físicos + MAC/VLAN |
| Sem controlos falsos | Feature bits dinâmicos; sem volume absoluto/HDMI fictício | Ativar apenas opções comprovadas no firmware |
| Recuperação | Backoff 60/120 s, reset 30 s e preservação de pairing | Desconexão autorizada ou natural; confirmar regresso |
| Testes/documentação | Pytest, Ruff e CI HACS/hassfest | Registar logs sanitizados e versão firmware |
| LAN sem cloud | JointSpace, WOL e DIAL só host configurado | Ensaio com WAN bloqueada só se Rui autorizar alteração de rede |
| Sem firmware/bypass | Nenhum código de factory reset/firmware; pairing normal | Não aplicável; nenhuma alteração feita na TV |

## Como registar prova real

Usar a ferramenta de leitura descrita no README. Registar estado físico observado,
hora, firmware, código HTTP, endpoint e resultado visível. Não guardar auth keys,
PINs, tokens, contas ou dumps de configuração. Para comandos, usar uma linha por
ensaio e distinguir explicitamente pedido aceite de ação executada.

Exemplo de **formato**, não resultado fictício:

| Cenário observado | Endpoint/comando | HTTP | Efeito visual | Conclusão |
|---|---|---|---|---|
| preencher após teste real | preencher | preencher | preencher | confirmado / inconclusivo |

A entrega do código instalável e dos testes simulados não encerra os gates de
hardware nem autoriza comandos que interrompam a utilização da TV. Não é ainda
uma declaração de integração estável e completamente validada na 55PUS8079/12.
