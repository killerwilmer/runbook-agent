---
servicio: payments-api
equipo: pagos
actualizado: 2026-09-30
---
# Runbook: payments-api

payments-api procesa los cobros y reembolsos. Habla con el proveedor de pagos externo (PagaFácil) y
guarda cada transacción en la base de datos `payments-db` (PostgreSQL). Es un servicio crítico: un
error aquí puede cobrarle mal a un cliente.

## Cobros duplicados

Es el incidente más grave de este servicio: siempre es SEV1, aunque afecte a pocos clientes.

Síntomas: clientes que reportan dos cargos por la misma compra, o la alerta `DuplicateChargeDetected`.

Mitigación inmediata:

1. Desactiva los reintentos automáticos hacia PagaFácil con el feature flag
   `payments.retry_enabled=false`. Los reintentos sin clave de idempotencia son la causa más común
   de los cobros duplicados.
2. Confirma que cada request a PagaFácil lleva el header `Idempotency-Key`. Si un deploy reciente lo
   quitó, haz rollback.
3. Exporta la lista de transacciones duplicadas para que el equipo de soporte haga los reembolsos.
   No reembolses a mano desde la consola del proveedor: el reembolso tiene que quedar registrado en
   payments-db.

## Timeouts del proveedor de pagos

Síntomas: pagos que fallan con `PSP_TIMEOUT` después de 10 segundos y la alerta
`PaymentProviderLatency`.

Revisa la página de estado de PagaFácil antes de tocar nada. Si el problema es del proveedor, no hay
nada que desplegar: activa el mensaje de "pagos con demora" en checkout y avisa a soporte. Si solo
falla una marca de tarjeta (por ejemplo Amex), es una degradación parcial: los clientes pueden pagar
con otra tarjeta.

## Errores de conexión con la base de datos

Síntomas: los logs muestran `ERR_CONN_REFUSED payments-db:5432` o `too many connections`.

1. Revisa cuántas conexiones hay abiertas en payments-db. El límite es 200.
2. Si un pod de payments-api tiene una fuga de conexiones, reinícialo (requiere aprobación del on-call
   de pagos).
3. Si la base está caída, escala de inmediato al equipo de plataforma: es SEV1.

## Escalamiento

Cualquier sospecha de pérdida de dinero (cobros duplicados, reembolsos que no se registran) es SEV1 y
se avisa al on-call de pagos y al líder del equipo en menos de 5 minutos.
