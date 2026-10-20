# Escritório dos Agentes

Escritório 3D no navegador para visualizar uma equipe de agentes de IA. Os agentes trabalham, fazem reunião e pausa, e um quadro na parede mostra o mapa de conexões do Segundo Cérebro.

Tudo fica em um único arquivo: [`escritorio-3d.html`](escritorio-3d.html). Ele usa Three.js r128, carregado por CDN.

## Como abrir

Dê dois cliques em **`abrir-escritorio.bat`**: ele liga um servidor local e abre o escritório no Chrome em http://127.0.0.1:8765/escritorio-3d.html.

**Instale uma vez a extensão** da pasta [`extensao`](extensao): abra `chrome://extensions`, ative o **Modo do desenvolvedor**, clique em **Carregar sem compactação** e escolha a pasta `extensao`. Com ela, cada monitor, a TV e a caixa de som viram navegadores de verdade (voltar, avançar, recarregar, início e barra de endereço), usando os logins que você já tem no Chrome. A extensão só tira o bloqueio de "abrir dentro de outro site" nas telas da aba do escritório.

| Tela | Abre em |
| --- | --- |
| PC 1 e PC 2 | claude.ai (relatórios diário e semanal) |
| PC 3 | planilha Leads tráfego |
| PC 4 e PC 5 | Google Agenda (lista e semana) |
| PC 6 | sistema do Cantinho do Au Au |
| TV | youtube.com completo, com busca, login e tudo |
| Caixa de som | open.spotify.com (player completo; o volume baixa com a distância) |

Sem a extensão, o escritório funciona com as telas limitadas abaixo:

| Objeto | O que abre |
| --- | --- |
| PC 1 e PC 2 | painel das tarefas agendadas do Claude (relatório diário e semanal) |
| PC 3 | planilha "Leads trafego" do Google Sheets |
| PC 4 e PC 5 | Google Agenda (lista e semana) |
| PC 6 | sistema do Cantinho do Au Au (cole o endereço na primeira vez) |
| TV | YouTube (cole um link na barra de cima) |
| Caixa de som | Spotify (cole um link de playlist, álbum ou música) |

Clique num monitor, na TV ou no painel do Spotify para "sentar": a câmera vai até a tela e o mouse passa a usar o site. **Esc** ou **Levantar** volta a andar.

### TV com busca do YouTube

O site do YouTube não pode abrir dentro de outra página, então a TV usa o player oficial do YouTube (com todos os controles) e uma busca própria. Para buscar, crie uma chave grátis da **YouTube Data API v3** em console.cloud.google.com e cole na TV na primeira busca. Sem chave, cole o link de um vídeo ou playlist.

### Caixa de som com Spotify

A caixa de som vira um aparelho chamado **Escritório 3D** na sua conta do Spotify, com playlists, controles e volume que muda com a distância. Precisa de **Spotify Premium** e de um app grátis em developer.spotify.com/dashboard com o Redirect URI `http://127.0.0.1:8765/escritorio-3d.html` (marque Web Playback SDK e Web API). Cole o Client ID no painel e clique em Conectar. Sem Premium, o painel tem um player simples.

O som ambiente tem posição: o teclado de quem está trabalhando, o ar-condicionado e a máquina de café ficam mais altos de perto. A TV e a caixa de som do Spotify (conectada) também baixam o volume conforme você se afasta.

Pela página do Claude (link do artifact), outros sites não podem aparecer dentro do escritório. Lá os computadores abrem as janelas do próprio escritório, com agenda e chat do Claude.

## Controles

| Ação | Como |
| --- | --- |
| Visão de cima | arrastar para girar, rolar para zoom |
| Andar pelo escritório | botão **Andar pelo escritório** |
| Olhar em volta | mover o mouse (entra em tela cheia com o mouse preso, como no Minecraft) |
| Pausar | **Esc** abre o menu de pausa (voltar, trocar visão, sair) |
| Girar sem mouse | Q / E ou setas ← → |
| Andar / correr / pular | W A S D ou setas / Shift / Espaço |
| Trocar 1ª ↔ 3ª pessoa | tecla **V** ou botão |
| Ver um agente | mirar com a cruz no centro e clicar |
| Mapa do Segundo Cérebro | clicar no quadro da parede ou no botão |

## O que é simulado

- Os 6 agentes (Ana, Bruno, Carla, Davi, Eva, Fábio) e as tarefas deles são dados de exemplo gerados na própria página.
- O mapa do Segundo Cérebro é uma foto das notas e dos links `[[...]]` lidos em 20/10/2026. Ele não se atualiza sozinho.

## Atualizar o mapa do Segundo Cérebro

`tools/gerar-grafo.py` lê uma pasta de notas Markdown e gera um JSON com as notas e os links `[[...]]` entre elas:

```bash
python tools/gerar-grafo.py "C:\caminho\para\segundo cerebro" grafo.json
```

Hoje os dados do mapa (`FOLDERS`, `NOTES` e `LINKS`) ficam escritos à mão no topo do script da página. O próximo passo é a página ler esse JSON diretamente.

## Próximos passos

- Conectar os agentes reais: o sistema de agentes envia eventos (`task_started`, `task_done`, `meeting`) por WebSocket ou SSE, e a página atualiza os bonecos.
- Fazer o mapa ler o JSON gerado pelo script, sem editar o HTML.
