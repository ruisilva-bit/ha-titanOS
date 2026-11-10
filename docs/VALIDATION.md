# Validação executada — candidato 0.2.0

## Ambiente real de execução dos testes

- Python 3.14.9, Linux; dependências instaladas via `uv sync --group dev`.
- Home Assistant **2026.10.1**, pytest-homeassistant-custom-component **0.13.372**.
- Ruff **0.16.6**; versões transitivas fixadas em `uv.lock`.
- Baseline upstream antes de alterações: **57 passed**.
- Suite candidata: **99 passed**, **0 failures**, **0 errors** (JUnit confirmado).
- `uv run ruff check .`: **No issues found**.
- `uv run ruff format --check .`: **33 files already formatted**.
- `git diff --check`: sem erros.
- Pesquisa por formatos de tokens GitHub/OpenAI e chaves privadas: zero resultados.
  A constante pública de interoperabilidade JointSpace herdada não é uma credencial
  pessoal; nenhum PIN/auth key real foi usado, guardado ou publicado.

## O que os testes demonstram

- Config flow: pairing manual/zeroconf, PIN válido/inválido, reauth e mudança de IP.
- Regressão: Cast fechado não bloqueia pairing nem causa discard do Standby.
- Reintrodução temporária do gate Cast → teste **falhou** com `tv_off`.
  Restauro da correção → suite completa **99 passed**. A regressão deteta o bug.
- Setup, unload e reload com preservação da Config Entry e sem pedir novo PIN.
- Payload/método/path, middleware Digest, timeout e erros HTTP ao nível do cliente.
- JSON inválido/tipos inesperados; HTTP 200 com erro semântico não é aceitação.
- Segredos de pairing não aparecem nos logs DEBUG; diagnósticos usam allowlist.
- Rede: backoff, indisponibilidade, recuperação e endpoints opcionais recusados.
- Máquina de estados: intenção não vira prova; unknown versus unavailable;
  standby duplicado/concorrente/timeout; WOL validado pelos bytes do magic packet.
- Remote: ordem, delay, aliases, repetição, recusa de hold e guard de energia.
- Ambilight: estilos, cores, menu, indisponibilidade e ausência de auto-restore.
- DIAL: XML namespaced, limites de corpo, rejeição de entidades XML, Origin,
  erros/timeouts e serviço HA de lançamento de registo detetado com opt-in.
- Opções alteram funcionalidades sem tocar nas credenciais existentes.

Os testes usam mocks explícitos; não são capturas da 55PUS8079/12 e não provam que
um comando aceite pelo HTTP foi executado fisicamente.

## Validação externa / hardware

- Pesquisa mDNS limitada neste host, cinco segundos: nenhum anúncio Philips/MQTT.
  Isso não prova ausência de serviços numa VLAN diferente.
- Não foi fornecido IP da TV nem versão da instalação Home Assistant do Rui.
- Não foi enviado Standby, WOL, alteração de input, launch, pairing, reset ou
  qualquer outro comando à TV real. Nenhuma configuração UniFi foi alterada.
- HACS e hassfest estão configurados em GitHub Actions; resultados do PR devem
  ser consultados no head exato. Não são declarados aprovados antes dessa execução.
- Revisão independente executada (sa-0-9f3834f3). Corrigidos: gate explícito
  de testes remotos e validação de auth_key da resposta de grant. Oito testes
  adicionais passam. O risco residual TLS é explícito no README: certificado
  autoassinado sem autenticação do servidor; usar LAN confiável, sem exposição.
- Primeira execução HACS falhou por faltar descrição/topics no repositório;
  metadados corrigidos e relidos. Hassfest aprovou o primeiro head. Os resultados
  finais devem ser lidos no head atualizado; nenhuma falha foi ignorada.

## Gate de release estável

Pendente: confirmar HA instalado, firmware, deteção LAN, prova de power nos vários
estados e ensaios físicos autorizados de comandos/WOL/Ambilight/DIAL. Até isso,
a entrega é um **candidato instalável para validação**, não certificação de todos
os critérios de hardware do pedido original. Ver `ACCEPTANCE.md`.
