# Philips Titan OS — Home Assistant (ha-titanOS)

Integração LAN para Philips Titan OS, adaptada de
[ksooo/ha-philips-titanos](https://github.com/ksooo/ha-philips-titanos).
Alvo: **Philips 55PUS8079/12 / TPN246E**.

> **Versão de validação, não certificada no hardware.** Os testes automatizados
> usam Home Assistant **2026.10.1**, Python **3.14.9** e respostas simuladas.
> A versão instalada pelo Rui e o IP da TV ainda não foram fornecidos.
> Não confundir testes simulados com prova de execução física.
> A API HTTPS acessível **não significa que o ecrã esteja ligado**.

## O que mudou

- Emparelhamento JointSpace HTTPS Digest **sem qualquer dependência da porta 8009**.
- Mantém domínio `philips_titanos`, versão de Config Entry 1, identificadores e
  formato `host` / `device_id` / `auth_key` / `mac`. **Não apagar a integração nem
  repetir o emparelhamento** ao substituir os ficheiros do original.
- Estado conservador: `unknown` se a API responde mas não existe evidência validada
  do ecrã; `unavailable` se falha a comunicação; `on` / `off` só com sinal fiável.
- `Standby` não é descartado por Cast fechado. Uma sondagem autenticada precede
  o comando; pedidos concorrentes são serializados e um toggle sem confirmação
  nunca é repetido automaticamente (nem após timeout). **O primeiro toggle com
  estado desconhecido também pode acordar a TV: confirmar visualmente antes.**
- Wake-on-LAN assíncrono, broadcast configurável e validação do MAC. O envio do
  pacote só significa `waking`, não significa que o ecrã ligou.
- Remote com teclas nativas, aliases, sequências, repetições e intervalo configurável.
- Media player com funcionalidades dinâmicas, sem HDMI fictício, volume absoluto
  ou aplicação ativa inventada. Mute não é atualizado de forma otimista.
- Ambilight opcional, apenas após confirmação no modelo; sem escritas automáticas
  para restaurar luz quando a TV acorda.
- DIAL opcional LAN em 56789: descobre registos YouTube, Netflix e AmazonInstantVideo
  por GET; permite lançamento explícito via POST e media browser. Respeita `Origin`.
  **Não é o catálogo completo de apps nem um detetor de aplicação em primeiro plano.**
- `DataUpdateCoordinator`: polling base 30 s; falhas com backoff 60/120/240/300 s,
  recuperação automática e reautenticação quando a TV devolve 401.
- Pedidos JointSpace serializados e espaçados ≥0,7 s. Não há dumps automáticos de
  listas de canais, nem retries de escritas potencialmente executadas.
- Sensor de ligação LAN e download de diagnósticos com campos permitidos, sem
  credenciais, IP/MAC/serial ou corpos completos de respostas.

## Instalação segura e preservação do emparelhamento

1. Confirmar **Home Assistant ≥2026.10.0**. Só 2026.10.1 foi exercitado nos testes;
   não assumir compatibilidade com versões antigas nem com a versão instalada.
2. Criar um **backup do Home Assistant**, incluindo configuração e registos.
   Guardar à parte a pasta atual `/config/custom_components/philips_titanos`.
   O backup contém credenciais: não o publicar nem o enviar pelo chat.
3. Desativar atualizações automáticas da integração original no HACS. Não manter
   dois repositórios HACS a gerir o mesmo domínio. **Não remover a Config Entry**.
4. Desativar temporariamente a integração na UI durante a substituição. Copiar
   **apenas** `custom_components/philips_titanos` deste projeto para
   `/config/custom_components/philips_titanos`, substituindo a pasta anterior
   (primeiro movê-la para o backup, fora de `custom_components`).
5. Reiniciar o Home Assistant numa janela em que o Rui autorize a interrupção.
   Este projeto não reinicia nem modifica automaticamente a instalação existente.
6. Reativar a entrada existente. Não editar `.storage` nem criar uma segunda TV.
   Configurar → **Reconfigurar** permite alterar o IP sem novo PIN; zeroconf
   também atualiza o IP quando o serial coincide.
7. Abrir **Configurar/Opções** e seguir a validação abaixo. Por segurança,
   funcionalidades ainda não validadas não aparecem no media player.

### HACS / atualização controlada

A estrutura é compatível com HACS (`hacs.json`, manifest, brand e workflow de
validação). Após merge da branch, adicionar
`https://github.com/ruisilva-bit/ha-titanOS` como repositório personalizado do tipo
**Integration**, substituindo a origem HACS anterior. Enquanto o código estiver
apenas no PR, usar os ficheiros da branch / pacote disponibilizado, pois `main`
ainda pode não conter a integração. Não ativar atualizações automáticas até à
validação física. Não foi criada uma release estável sem testes no hardware.

## Validação na televisão real

### 1. Leituras, sem interrupção

Executar num terminal local de confiança, na rede da TV:

```bash
python3 tools/probe_tv.py IP_DA_TV
python3 tools/probe_tv.py IP_DA_TV --paired
```

O segundo comando pede **as credenciais JointSpace existentes em prompts
mascarados**, não emparelha nem guarda segredos. Não colocar credenciais em flags,
ficheiros novos, issues ou chat. Não executar este script por uma interface que
não permita introdução mascarada. Não solicitar nem partilhar dumps de `.storage`.

O script só faz ligações TCP a um host e GETs documentados e espaçados. Não faz
scan de rede, POST, pairing, MQTT login, alterações de segurança ou controlos.
O relatório não inclui corpos brutos, nomes de conta ou identificadores da TV.
Guardar localmente resultados em três situações observadas fisicamente:

- TV ligada com ecrã visível;
- standby rápido, usando o comando físico quando for conveniente;
- standby prolongado, sem desligar fisicamente a alimentação.

Não concluir que `On` em `powerstate` é verdadeiro se também ocorre com o ecrã
apagado. Porta aberta, `activities/current`, MQTT conectado e DIAL `running`
também não provam ecrã ligado. Não ativar `powerstate_verified` nesse caso.
Uma falha de rede não distingue deep standby de TV desligada da corrente.

### 2. Teclas (apenas numa janela autorizada)

Nas opções, ativar temporariamente `remote_testing` antes dos primeiros ensaios.
Por defeito o remote recusa teclas/desligar enquanto não houver validação nem
modo de teste explícito. Depois de validar, ativar `keys_verified` e desligar
`remote_testing`. Ligar por WOL exige sempre a sua opção própria.

Ferramentas de Programador → Ações:

```yaml
action: remote.send_command
target:
  entity_id: remote.A_ENTIDADE_DA_TUA_TV
data:
  command: [Home, CursorDown, Confirm, Back]
  delay_secs: 1
  num_repeats: 1
```

Testar individualmente `VolumeUp`, `VolumeDown`, `Mute`, `Source` e observar o
resultado. A resposta HTTP é apenas aceitação do pedido. Usar `Source` + setas
para seleção manual; **não existem macros HDMI numeradas garantidas**.
Aliases disponíveis: `up`, `down`, `left`, `right`, `ok`, `home`, `back`.
Teclas adicionais documentadas nos clientes de referência incluem Play, Pause,
Stop, Rewind, FastForward, ChannelStepUp/Down, cores, Info, Options, WatchTV e
Digit0–Digit9; continuam por validar neste modelo. Hold não é suportado.

**Antes de enviar `Standby`, confirmar autorização e que a TV está ligada.**
Enviar uma vez por `remote.send_command`; observar o resultado. Se não houver
sinal de power fiável, pedidos seguintes são bloqueados, mesmo que expire a
transição. Confirmar fisicamente o ecrã e recarregar a integração para rearmar
explicitamente o teste. Recarregar nunca deve ser usado como retry automático.

### 3. Opções / funcionalidades dinâmicas

| Opção | Quando ativar |
|---|---|
| `remote_testing` | Ativar temporariamente para ensaios explícitos autorizados via remote; não significa suporte confirmado. |
| `keys_verified` | Após volume e Standby terem efeito visual confirmado. Mostra volume ± e desligar no media player. |
| `wol_verified` | Ativar para ensaio autorizado de WOL; manter só se o ecrã ligar. Precisa de MAC com WOL indicado pela TV. |
| `broadcast` | Broadcast IPv4 da VLAN da TV, quando necessário. Não alterar router/firewall sem autorização. |
| `powerstate_verified` | Só se `/6/powerstate` distingue realmente ON e standby. Se não, manter desligado e aceitar `unknown`. |
| `mute_state_verified` | Só se `muted` acompanha comando físico e não é apenas eco da API. |
| `ambilight_verified` | Testar apenas quando o modelo anuncia Ambilight e os endpoints/menu correspondem. |
| `dial_verified` | Ativar para descobrir registos DIAL. Testar lançamento explicitamente; desativar se não tiver efeito no ecrã. |

As opções não alteram credenciais e provocam reload da entrada. WOL usa o MAC
já guardado no pairing. Se a API não fornecer MAC/WOL, não aparece ligar;
recolher evidência antes de implementar uma escolha manual de interface.
Wake-on-WLAN depende do firmware/configuração da TV. Broadcast entre VLANs pode
ser bloqueado: não é motivo para inventar sucesso nem abrir portas automaticamente.

Exemplo de lançamento DIAL, depois de ativar e confirmar o registo:

```yaml
action: media_player.play_media
target:
  entity_id: media_player.A_ENTIDADE_DA_TUA_TV
data:
  media_content_type: app
  media_content_id: YouTube
```

Não é efetuado launch ao iniciar/recarregar. A descoberta repete-se no máximo a
cada cinco minutos durante polls bem-sucedidos. DIAL depende atualmente da entrada
JointSpace carregada; não constitui uma integração independente de fallback.

### 4. Falhas e regresso à rede

Após autorização, observar uma desconexão natural ou uma indisponibilidade de
rede controlada. Esperado: `unavailable`, sensor LAN desligado e backoff; ao
regressar a API, retoma sem novo PIN. Não mudar firewall nem desligar serviços
críticos só para este teste. Credenciais recusadas com 401 iniciam reautenticação;
403/404/405 de endpoints opcionais suspendem essa funcionalidade até reload,
sem classificar a TV inteira como offline. Um 403 no endpoint essencial de
atividade é tratado como falha, não como autorização válida.

## Limitações e estado das funcionalidades

Ver [investigação e matriz de evidência](docs/RESEARCH.md) e
[aceitação por cenário](docs/ACCEPTANCE.md).

- Nenhum comando foi enviado à Philips 55PUS8079/12 por este trabalho.
- MQTT local está **investigado, mas não implementado/confirmado no modelo**.
  Requer pairing próprio e novas credenciais, sujeito a autorização do Rui.
  A listagem de apps via tópico `proxy` da referência chama a API cloud Titan;
  não foi incorporada numa solução prometida como LAN independente de cloud.
- DIAL é apenas o subconjunto de registos presentes, não apps arbitrárias.
- HDMI direto, app ativa e volume absoluto não são anunciados. A atividade
  `extension` só identifica HDMI genericamente, não uma entrada numerada.
- `deep_standby` está reservado para futura evidência explícita. Falha de rede
  resulta em `unavailable`, não em `off`. Não há um sensor físico inventado.
- Os limites de 0,7 s / 30 s são mitigação conservadora baseada nas referências,
  não garantias do firmware TPN246E. Interromper testes se TLS começar a falhar.
- TLS JointSpace usa certificado autoassinado sem SAN (`ssl=False`), conforme
  o original. A TV não é autenticada pelo TLS: um atacante na LAN pode fazer
  MITM, observar pairing e adulterar respostas/comandos. Não há pinning de
  certificado nesta versão. Usar apenas em LAN de confiança e isolada;
  não expor portas publicamente.
- Não há cloud, alteração de firmware, factory reset ou bypass de segurança.

## Desenvolvimento e testes

```bash
uv sync --locked --group dev
uv run ruff format --check .
uv run ruff check .
uv run pytest -q --junitxml=test-results.xml
```

As dependências de desenvolvimento estão fixadas no `uv.lock`. O runtime usa
as bibliotecas já presentes no HA, sem dependências extras no manifest.
GitHub Actions executa testes, Ruff, hassfest e validação HACS. Resultados reais
e eventuais limitações dos validadores são registados em `docs/VALIDATION.md`.

## Rollback

1. Fazer backup do estado atual e guardar diagnósticos sanitizados.
2. Com autorização de restart, desativar a entrada e restaurar a **pasta original
   completa** `custom_components/philips_titanos` a partir do backup.
3. Reiniciar HA e reativar a mesma Config Entry. Não alterar nem apagar credenciais
   ou registos de entidades. O domínio/versão não mudaram e não há migração destrutiva.
4. Rever no HACS qual repositório gere a pasta antes de reativar atualizações.
5. Se necessário, restaurar o backup completo do HA. O rollback ao original pode
   repor a dependência da porta 8009; essa limitação é conhecida.

## Licenças

Código adaptado de `ksooo/ha-philips-titanos` conserva **Apache-2.0**, disponível
em `LICENSE.upstream`; ficheiros alterados estão assinalados e `NOTICE` identifica
origem e alterações. `LICENSE` MIT do repositório do Rui é preservada; não
relicencia o código Apache importado. As outras referências foram estudadas como
documentação de protocolo, sem copiar código sem licença identificada.
