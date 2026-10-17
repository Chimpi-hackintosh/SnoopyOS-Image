# SnoopyOS 0.1 Lite Preview

Linux live de 64 bits com base Debian 13.7 e área de trabalho Xfce personalizada

O limite da imagem é **menos de 2 GiB**, ou seja, **menos de 2.147.483.648 bytes**
A construção falha se a ISO atingir esse limite

## O que fica

- Papel de parede azul com curvas verdes e azuis, barra creme e menu Snoopy +
- Terminal, Thunar, Firefox ESR com português, áudio e rede
- Instalador Calamares e boot híbrido BIOS/UEFI
- Firmware básico Atheros, Intel Wi-Fi e Realtek

## Reduções

- LibreOffice, suas traduções e ajuda
- Fontes Noto extras e CJK
- Métodos de entrada IBus e ajuda extra do GIMP
- Traduções do Firefox e da interface além de português e inglês
- Firmwares adicionais, incluindo AMD/NVIDIA/Intel gráficos, alguns áudios e redes
- Arquivos do Debian Installer, UDEBs, cópia do pacote do kernel e firmwares do repositório da mídia

Os módulos do kernel e as bibliotecas gráficas permanecem
Os documentos de licença dos programas mantidos permanecem
Alguns computadores físicos precisarão instalar firmware adicional para gráficos, som ou rede

O repositório local que o Calamares usa para instalar GRUB é preservado e seus índices são atualizados
A lista exata dos pacotes selecionados está em `pacotes-removidos.json`

## Usar

Baixe a ISO única e o `SHA256SUMS.txt` na Release
No Windows, confira com `Get-FileHash .\SnoopyOS-0.1-Lite-amd64.iso -Algorithm SHA256`
Abra a ISO como unidade óptica de uma máquina virtual de 64 bits
Use aproximadamente 3 GiB de RAM para experimentar a área de trabalho

O usuário live é `snoopy` e a senha é `live`
`Ctrl + Alt + T` abre o Terminal e `Super` abre o menu
O modo live não persiste as alterações após desligar
Montar o arquivo ISO no Windows só abre seus arquivos
Para iniciar o sistema é necessário dar boot pela imagem

## Construir

Em Linux amd64 com `sudo`, `python3`, `xorriso` e `squashfs-tools`:

```sh
sudo bash lite/build.sh /caminho/debian-live-13.7.0-amd64-xfce.iso /caminho/SnoopyOS-0.1-Lite-amd64.iso
```

Reserve aproximadamente 20 GiB de espaço livre para a base, extração e saída
A base oficial é verificada pelo SHA-256 registrado em `remaster/BASE-DEBIAN.json`
As remoções são feitas pelo APT com serviços desativados dentro de um chroot
A consistência do dpkg, as dependências, o catálogo BIOS/UEFI e o tamanho final são verificados

Esta edição é uma prévia de desenvolvimento
A instalação completa em disco e a compatibilidade com todos os computadores não foram validadas
