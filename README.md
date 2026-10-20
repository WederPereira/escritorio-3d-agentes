# Escritório dos Agentes

Escritório 3D no navegador para visualizar uma equipe de agentes de IA. Os agentes trabalham, fazem reunião e pausa, e um quadro na parede mostra o mapa de conexões do Segundo Cérebro.

Tudo fica em um único arquivo: [`escritorio-3d.html`](escritorio-3d.html). Ele usa Three.js r128, carregado por CDN.

## Como abrir

Dê dois cliques em **`abrir-escritorio.bat`**. Ele liga um servidor local e abre o escritório no Chrome em http://localhost:8765/escritorio-3d.html.

Nessa versão do computador, os monitores, a TV e a caixa de som mostram sites de verdade:

| Objeto | O que abre |
| --- | --- |
| PC 1 e PC 2 | painel das tarefas agendadas do Claude (relatório diário e semanal) |
| PC 3 | planilha "Leads trafego" do Google Sheets |
| PC 4 e PC 5 | Google Agenda (lista e semana) |
| PC 6 | sistema do Cantinho do Au Au (cole o endereço na primeira vez) |
| TV | YouTube (cole um link na barra de cima) |
| Caixa de som | Spotify (cole um link de playlist, álbum ou música) |

Clique num monitor, na TV ou no painel do Spotify para "sentar": a câmera vai até a tela e o mouse passa a usar o site. **Esc** ou **Levantar** volta a andar.

O som ambiente tem posição: o teclado de quem está trabalhando, o ar-condicionado e a máquina de café ficam mais altos de perto. A TV também baixa o volume conforme você se afasta. O Spotify não deixa outra página mexer no volume, então ele toca sempre no mesmo volume.

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
