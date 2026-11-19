---
servicio: payments-api
equipo: pagos
severidad: SEV1
fecha: 2026-09-23
actualizado: 2026-09-30
---
# Postmortem PM-2026-011: cobros duplicados en payments-api

## Resumen

El 23 de septiembre, durante 35 minutos, 312 clientes recibieron dos cargos por la misma compra. El
problema empezó con el deploy de payments-api 2.8.0, que cambió el cliente HTTP hacia PagaFácil.
Severidad: SEV1 (pérdida de dinero para los clientes).

## Causa raíz

El cliente HTTP nuevo reintentaba automáticamente las peticiones que tardaban más de 3 segundos, pero
ya no enviaba el header `Idempotency-Key`. PagaFácil procesó cada reintento como un cobro nuevo.

## Detección

Soporte recibió los primeros reclamos 20 minutos después del deploy. No había una alerta de cobros
duplicados: la creamos después de este incidente (`DuplicateChargeDetected`).

## Mitigación

Se desactivaron los reintentos con el feature flag `payments.retry_enabled=false` y después se hizo
rollback a la versión 2.7.4. Los 312 reembolsos se registraron en payments-db y se procesaron en las
siguientes 24 horas.

## Qué aprendimos

- Un reintento sin idempotencia, en un sistema de pagos, es un cobro nuevo.
- El feature flag de reintentos detuvo los cobros duplicados en segundos, sin esperar el rollback.

## Acciones

- Test de contrato que falla si una petición a PagaFácil no lleva `Idempotency-Key` (hecho).
- Alerta `DuplicateChargeDetected` (hecho).
