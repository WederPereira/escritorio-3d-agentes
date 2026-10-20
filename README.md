# Escritório dos Agentes

Escritório 3D no navegador para visualizar uma equipe de agentes de IA. Os agentes trabalham, fazem reunião e pausa, e um quadro na parede mostra o mapa de conexões do Segundo Cérebro.

Tudo fica em um único arquivo: [`escritorio-3d.html`](escritorio-3d.html). Ele usa Three.js r128, carregado por CDN.

## Como abrir

Abra `escritorio-3d.html` direto no navegador, ou sirva a pasta localmente:

```bash
python -m http.server 8765
```

Depois acesse http://localhost:8765/escritorio-3d.html.

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
