---
servicio: notifications-worker
equipo: plataforma
actualizado: 2026-07-22
---
# Runbook: notifications-worker

notifications-worker consume la cola `notifications` de RabbitMQ y envía correos y notificaciones push
(confirmación de compra, envío, recuperación de contraseña).

## Cola acumulada (QueueBacklog)

La alerta `QueueBacklog notifications > 1000` significa que los mensajes llegan más rápido de lo que
el worker los procesa.

1. Revisa si el proveedor de correo responde. Si devuelve `429 Too Many Requests`, el worker está
   limitado por el proveedor: escalar réplicas no ayuda y empeora el bloqueo.
2. Si el proveedor está bien, escala el worker: `kubectl -n plataforma scale deployment/notifications-worker --replicas=4`.
3. Revisa la cola de mensajes muertos (`notifications.dlq`). Un mensaje mal formado que falla en bucle
   puede frenar a todos los demás.

Un retraso en las notificaciones es SEV3, salvo que afecte la recuperación de contraseña de forma
masiva, que impide el acceso: en ese caso es SEV2.

## Correos duplicados

Si los clientes reciben el mismo correo varias veces, el worker está reprocesando mensajes porque no
confirma (ack) a tiempo. Revisa el `prefetch` y el tiempo de procesamiento por mensaje.
