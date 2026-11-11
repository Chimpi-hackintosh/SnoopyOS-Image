# SnoopyOS Earthquake Alert System (EAS)

Monitor informativo de terremotos para as edições Lite e Games.

- Consulta o feed global GeoJSON de terremotos de magnitude 4.5+ do USGS, atualizado periodicamente.
- Exibe magnitude, local e país/região quando o nome do local permite identificar o país.
- Mostra bandeiras para países reconhecidos e usa um globo como alternativa.
- A magnitude é dinâmica; **7.8 é apenas um exemplo**, não um valor fixo.
- O limiar pode ser ajustado pela variável \`SNOOPYOS_EAS_MIN_MAGNITUDE\` (mínimo permitido: 4.5).
- Requer conexão com a internet e GTK 3 / PyGObject.
- Se a consulta falhar, o sistema não inventa eventos nem mostra um alerta falso.

**Segurança:** o EAS não desliga o computador. A janela do aviso fecha automaticamente após 60 segundos, ou pode ser fechada pelo usuário. Desligar o computador durante uma emergência poderia interromper informações úteis. O aviso é informativo e não substitui alertas oficiais nem as instruções das autoridades locais.

Fonte dos dados: [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_hour.geojson).
