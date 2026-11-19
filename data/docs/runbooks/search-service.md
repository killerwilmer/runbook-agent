---
servicio: search-service
equipo: plataforma
actualizado: 2026-10-05
---
# Runbook: search-service

search-service responde las búsquedas de la tienda sobre un índice de Elasticsearch
(`products-v{N}`). No es un servicio crítico: si falla, los usuarios todavía pueden navegar por
categorías y comprar.

## La búsqueda devuelve resultados vacíos

La causa más común es un reindexado nocturno que falló a medias: el alias `products` quedó apuntando
a un índice nuevo y vacío.

```bash
curl -s elastic.internal:9200/_cat/aliases/products
curl -s elastic.internal:9200/_cat/indices/products-*
```

Mitigación: apunta el alias de vuelta al índice anterior, que todavía tiene datos. No borres el índice
vacío hasta entender por qué falló el job.

Resultados vacíos para todos los usuarios, con la navegación por categorías funcionando, es SEV2: una
función importante está caída, pero existe un rodeo.

## Latencia alta

La alerta `HighLatency search-service p99 > 2s` suele aparecer cuando el clúster de Elasticsearch está
haciendo un merge de segmentos o cuando hay consultas con comodines al inicio (`*zapato`). Revisa las
consultas lentas en el slow log antes de escalar el clúster.
