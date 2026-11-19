---
servicio: catalog-service
equipo: checkout
actualizado: 2026-08-18
---
# Runbook: catalog-service

catalog-service sirve los productos, precios y fotos de la tienda. Las imágenes se entregan desde la
CDN; los datos de productos se cachean en Redis (`redis-catalog`) durante 10 minutos.

## Las imágenes no cargan

Si las imágenes fallan solo en un navegador (por ejemplo Safari), casi siempre es un problema de
formato: Safari antiguo no soporta algunas imágenes AVIF. Es un incidente menor (SEV3): los usuarios
ven el producto sin foto, pero pueden comprar.

Si fallan en todos los navegadores, revisa el estado de la CDN y los certificados del dominio
`img.tienda.com`.

## Precios desactualizados

Síntoma: la tienda muestra un precio distinto al que se cobra en checkout. Es grave porque genera
reclamos y cobros incorrectos.

Mitigación: invalida la caché de precios.

```bash
kubectl -n checkout exec deploy/catalog-service -- ./bin/cache-invalidate --prefix=price:
```

Si el problema vuelve después de invalidar, revisa el job que sincroniza precios desde el ERP.

## Catálogo caído

Si catalog-service no responde, la tienda no muestra productos y nadie puede comprar: es SEV1. Sigue
el mismo diagnóstico que en checkout-api (pods, deploy reciente, rollback).
