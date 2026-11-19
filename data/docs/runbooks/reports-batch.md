---
servicio: reports-batch
equipo: plataforma
actualizado: 2026-09-02
---
# Runbook: reports-batch

reports-batch es un CronJob que corre todas las noches a las 02:00 y genera los reportes de ventas para
el equipo comercial. Es un servicio interno y no crítico: si falla, los clientes no lo notan.

## El job nocturno falló (JobFailed)

1. Mira los logs del último intento:
   `kubectl -n plataforma logs job/reports-batch-<fecha>`
2. Las causas más comunes son un timeout contra la réplica de lectura de la base de datos y la falta de
   espacio en el bucket de reportes.
3. Cuando esté corregido, relánzalo a mano:
   `kubectl -n plataforma create job --from=cronjob/reports-batch reports-batch-manual`

Un reporte que no se generó es SEV3: se atiende en horario laboral. Avisa al equipo comercial a qué
hora estará disponible.

## El job tarda demasiado

Si el job sigue corriendo a las 08:00, compite con el tráfico de la mañana por la réplica de lectura.
Cancélalo y relánzalo después de las 22:00.
