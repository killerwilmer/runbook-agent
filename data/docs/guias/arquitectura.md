---
equipo: plataforma
actualizado: 2026-09-15
---
# Arquitectura de la tienda

La tienda online corre en un clúster de Kubernetes (`prod-us-east`) con un namespace por equipo:
`checkout`, `pagos`, `identidad` y `plataforma`.

## Servicios y dependencias

- **checkout-api** depende de payments-api (cobrar), auth-service (validar el token del usuario) y
  catalog-service (precios). Si cualquiera de los tres falla, el checkout falla.
- **payments-api** depende del proveedor externo PagaFácil y de la base `payments-db` (PostgreSQL).
- **auth-service** guarda las sesiones en `redis-sessions` y publica sus claves en el JWKS.
- **catalog-service** lee productos de `catalog-db` y los cachea en `redis-catalog`; las imágenes
  salen de la CDN.
- **search-service** consulta un clúster de Elasticsearch que se reindexa todas las noches.
- **notifications-worker** consume la cola `notifications` de RabbitMQ.
- **reports-batch** lee de la réplica de lectura de las bases de datos.
- **admin-dashboard** es la herramienta interna de operaciones; lee de las mismas APIs.

## Servicios críticos

checkout-api, payments-api, auth-service y catalog-service son críticos: si alguno falla, los clientes
no pueden comprar o entrar. Los demás afectan funciones secundarias o a usuarios internos.

## Observabilidad

Las métricas están en Prometheus y los tableros en Grafana (`grafana.internal`). Los logs se consultan
con `kubectl logs` o en Loki. Las alertas llegan a #alertas-prod y las de severidad alta, también a
PagerDuty.
