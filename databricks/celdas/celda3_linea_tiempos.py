# Databricks notebook source
# Pegar AL FINAL de la celda 3 de 99_ejecutar_todo (la de bronze → silver → gold → control).
# Guarda cuánto demoró cada etapa en el Volume (40_tiempos/<carga>.json); el notebook 08_demo lo lee para comparar.
import json, os, datetime; os.makedirs('/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27/40_tiempos', exist_ok=True)
with open(f'/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27/40_tiempos/{CARGA}.json', 'w') as f: json.dump(dict(carga=CARGA, fecha=datetime.datetime.now().isoformat(timespec='seconds'), **{k: round(v, 1) for k, v in tiempos.items()}), f)
print('tiempos guardados:', {k: f'{v:.0f} s' for k, v in tiempos.items()})
