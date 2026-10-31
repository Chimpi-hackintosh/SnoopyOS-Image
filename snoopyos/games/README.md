# 🐾 SnoopyOS Games 0.2 Preview

Edição gamer do SnoopyOS, derivada da base Debian/Xfce da versão Lite

**Importante:** 1000 FPS não são garantidos pelo sistema. O FPS depende do jogo, GPU, CPU, drivers e configurações

## Recursos

- Widgets GTK3 com tema escuro azul/roxo, cartões de CPU, RAM, espaço livre e modo FPS
- Modo FPS reversível: desativa o compositor Xfce enquanto ativado e restaura ao sair, sem root
- Integração opcional com `gamemoderun`, quando GameMode já estiver instalado
- Limpeza segura antes de iniciar jogos pelo lançador Games, removendo miniaturas antigas e temporários próprios
- Não toca em saves, shaders dos jogos, Downloads, Steam, Documentos nem configurações pessoais
- Python 3 e GTK3/PyGObject, sem Electron nem serviço pesado

## Executar

```bash
python3 snoopyos/games/games.py widget
python3 snoopyos/games/games.py status
python3 snoopyos/games/games.py cleanup --days 7
python3 snoopyos/games/games.py play -- /caminho/do/jogo
```

O botão Escolher jogo inicia executáveis Linux; jogos Steam também podem ser abertos pelo próprio Steam. A limpeza automática só ocorre quando o jogo é iniciado pelo lançador Games

A limpeza só apaga arquivos regulares com pelo menos sete dias nas pastas de miniaturas e `~/.cache/snoopyos-games/tmp`, sem seguir links simbólicos. O espaço liberado depende do cache existente

## Construção da edição Games

Em Linux amd64, com as ferramentas da [receita Lite](../lite/README-Lite.md):

```bash
sudo bash snoopyos/games/build.sh /caminho/debian-live-13.7.0-amd64-xfce.iso /caminho/SnoopyOS-0.2-Games-amd64.iso
```

A receita mantém verificação SHA-256 da base, o limite da ISO menor que 2 GiB e testes de boot antes da publicação. Instalação completa em disco ainda não validada

**Estado:** [ISO Games Preview publicada em 31/10/2026](https://github.com/Chimpi-hackintosh/SnoopyOS-Image/releases/tag/v0.2-games.1), com SHA-256 e boot UEFI/QEMU verificados pelo workflow

[Baixar a ISO Games](https://github.com/Chimpi-hackintosh/SnoopyOS-Image/releases/download/v0.2-games.1/SnoopyOS-0.2-Games-amd64.iso) · [Conferir o SHA-256](https://github.com/Chimpi-hackintosh/SnoopyOS-Image/releases/download/v0.2-games.1/SHA256SUMS.txt)

A instalação completa em disco permanece sem validação. Correções posteriores no código exigem uma nova construção para aparecer na ISO

