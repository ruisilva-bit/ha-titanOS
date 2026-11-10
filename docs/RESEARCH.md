# Investigação técnica e evidência

## Fontes fixadas

| Projeto | Revisão analisada | Resultado |
|---|---|---|
| ksooo/ha-philips-titanos | `d23ef23d98d6ce9a54371a147d140494e3152fc3` | Base Apache-2.0; API, flow, coordinator, entities, testes e MAINTENANCE lidos. Baseline: 57 testes passaram antes de alterações. |
| bedirhanyildirim/philips-titan-os-55pml9019-remote | `4db4cb4d109030ccb194413665aa918270584c58` | README, TITAN_OS_API.md e cliente MQTT analisados. Refere 55PML9019/12, não a TV do Rui. MIT. |
| daCream87/uc-philips-titanos | `cf0207a0261288e5e0ebb2af248f5a160a4e99f8` | Cliente, mapeamento e comportamento de power/source analisados. Não foi encontrada licença no checkout; nenhum código copiado. |

Issue upstream [#1](https://github.com/ksooo/ha-philips-titanos/issues/1)
descreve emparelhamento bloqueado por Cast filtrado noutro modelo. Thread consultada,
sem comentários devolvidos. Não havia PRs abertos nas pesquisas `standby` e
`pairing`, nem PR existente no repositório alvo no início do trabalho.

## Causas identificadas no código original

1. `api.is_on()` abre TCP 8009. `config_flow.async_step_pair()` exige `is_on()`
   antes de pedir PIN em 1926. Uma porta sem relação com pairing bloqueia-o.
2. Coordinator retorna off sem consultar API quando Cast está fechado.
   `async_turn_off()` retorna sem enviar Standby quando `data.is_on` é falso.
3. `expect_power()` transforma intenção de comando em on/off, sem confirmação.
4. `_request()` registava os primeiros 500 caracteres de **todas** as respostas,
   incluindo respostas de pairing que podem conter auth keys. Removido: apenas
   método/caminho/status são registados, e erros de pairing não incluem payloads.
5. Endpoints opcionais e dumps de canais podem impedir o polling; o firmware da
   referência relata bloqueios TLS sob carga. Removidos dumps automáticos,
   isolamento de endpoints opcionais e serialização/limitação de pedidos.
6. A referência Unfolded Circle faz retries genéricos incluindo POST, assume ON
   quando não existe um powerstate JSON válido e pode atualizar OFF de forma
   otimista. Não foram reproduzidas essas escolhas.

## Protocolos alternativos: o que se sabe e o que NÃO se sabe

- **JointSpace v6, HTTPS 1926**: caminhos e autenticação existentes preservados.
  `POST /6/input/key` com `{"key":"Confirm"}` etc. HTTP 200 significa aceitação
  pelo serviço; o efeito físico continua por confirmar.
- **Powerstate**: upstream TPN256E relata 404; a referência MQTT relata `On`
  mesmo em standby rápido. Não é usado como autoridade por defeito. O utilizador
  só o ativa depois de correlacionar leituras com ecrã físico nos vários estados.
- **Screenstate**: upstream relata Off com imagem visível; apenas sondado pela
  ferramenta de diagnóstico, não usado como autoridade.
- **MQTT 8883**: referência documenta MQTT5/TLS, CA Titan, retained `info`, pairing
  PIN separado e HMAC-SHA256, reply topics/CorrelationData, teclas `rc` e `deeplink`.
  Ainda não foi observado neste modelo. Conectar não prova ecrã ligado. Não foi
  iniciado pairing nem armazenada credencial nova. Backend MQTT não implementado.
- **Cloud disfarçada de local**: `proxy /v1/me/user_apps`, `api=gaea`, faz chamadas
  à API autenticada Titan cloud na referência; não satisfaz por si só uma garantia
  de inventário de aplicações offline. YouTube Lounge usa endpoints externos e foi
  excluído. Nenhum desses caminhos foi incorporado.
- **DIAL 56789**: GET/POST `/apps/YouTube`, `/apps/Netflix`, `/apps/AmazonInstantVideo`,
  Origins YouTube/Netflix conforme documentação. Backend implementado, opt-in;
  descobre apenas registos com XML válido. Sem launch automático, sem app inventada,
  sem interpretar `running` como foreground ou power.
- **HDMI**: referências usam macros incompatíveis (âncora no topo ou fundo do menu,
  ordens diferentes). Não é seguro generalizar. Source manual disponível; seleção
  direta HDMI não anunciada. Não foram tentadas teclas HDMI especulativas.
- **UPnP/SSDP/mDNS**: referências descrevem DIAL/dd.xml e mDNS seguro MQTT. Foi
  realizada apenas pesquisa mDNS limitada de `_philipstv_s_rpc._tcp` e
  `_secure-mqtt._tcp` neste host durante cinco segundos: **zero anúncios recebidos**.
  Isto não prova ausência de serviço; VLAN/multicast podem impedir descoberta.
  Não foi realizado scan de sub-rede nem qualquer alteração UniFi.
- **WOL/WoWLAN**: pacote UDP 9 implementado. O efeito depende de interface/MAC,
  VLAN, broadcast e firmware. Nenhum pacote foi enviado à TV real neste trabalho.

## Matriz de compatibilidade no modelo 55PUS8079/12

Estados pedidos: **confirmado**, **detetado mas por validar**,
**não suportado ou indisponível**. Acrescentamos a origem da evidência para não
confundir o relato fornecido pelo Rui com observações desta execução.

| Capacidade | Estado no modelo | Evidência / interpretação |
|---|---|---|
| GET /6/system em 1926 | Confirmado (relato do Rui) | HTTP 200 anterior; não prova ecrã ligado. |
| Pairing JointSpace sem Cast | Confirmado (relato do Rui) | PIN já concluído após remover gate; regressão coberta por simulação. |
| TCP 8009 | Não suportado ou indisponível (relato do Rui) | Inacessível mesmo com TV ligada; não usado. |
| Volume/Standby/navegação/Mute | Detetado mas por validar | Integração emparelhada; comandos não funcionam corretamente segundo pedido; efeito específico ainda sem medições. |
| Powerstate / screenstate | Não suportado ou indisponível para validação | Sem IP/respostas desta TV; NÃO é uma conclusão de ausência de suporte. |
| WOL / WoWLAN | Não suportado ou indisponível para validação | Sem MAC e ensaio físico; implementação comprovada por teste do pacote. |
| MQTT 8883 | Não suportado ou indisponível para validação | Referência noutro modelo; não detetado nesta TV. |
| DIAL 56789 / UPnP | Não suportado ou indisponível para validação | Backend DIAL simulado; falta deteção no IP real. |
| Ambilight | Não suportado ou indisponível para validação | Não assumir só pelo modelo; entity requer indicação da API e opt-in. |
| HDMI direto / apps MQTT / app ativa / volume absoluto | Não suportado ou indisponível nesta versão | Deliberadamente não anunciados; não se conclui impossibilidade do hardware. |

Não houve acesso ao endereço da TV nem à instalação HA. Nenhuma capacidade de
controlo físico está a ser promovida a confirmada com base em testes unitários.
Não é possível provar impossibilidade de um protocolo sem observar este firmware.

## Máquina de estados

`unknown` → observação explícita fiável → `on` ou `quick_standby`.
Comando WOL → `waking`; comando Standby → `standby_pending`; ambos são intenções.
Após deadline sem confirmação → `unknown`. Falha de comunicação → `unavailable`.
`deep_standby` está reservado: rede silenciosa não o distingue de TV sem corrente
ou falha de VLAN. Não inferir off pela ausência de porta, por timeout ou por HTTP.
O latch de Standby sobrevive a polls sem evidência e timeouts, mas não a reload;
reload é uma ação manual após confirmar fisicamente o estado, nunca um retry.
