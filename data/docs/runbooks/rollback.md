---
equipo: plataforma
actualizado: 2026-10-01
---
# Runbook: rollback de un deploy

Hacer rollback es volver a la versión anterior de un servicio. Es la mitigación más rápida cuando un
incidente empieza después de un deploy: primero se restaura el servicio y después se investiga la
causa con calma.

## Cuándo hacer rollback

- El incidente empezó en los 30 minutos siguientes a un deploy del servicio afectado.
- La versión anterior no tiene cambios de base de datos incompatibles. Si el deploy incluyó una
  migración, consulta al equipo dueño antes: volver atrás el código sin volver atrás la migración puede
  romper más cosas.

## Cómo hacer rollback

Todo rollback en producción requiere la aprobación del on-call del equipo dueño del servicio, y queda
registrado en el canal del incidente.

```bash
kubectl -n <namespace> rollout undo deployment/<servicio>
kubectl -n <namespace> rollout status deployment/<servicio> --timeout=5m
```

Si el servicio se despliega con Argo CD, desactiva primero la sincronización automática; si no, Argo
vuelve a desplegar la versión con el problema.

## Después del rollback

1. Confirma que la tasa de errores y la latencia volvieron a lo normal durante al menos 10 minutos.
2. Bloquea la versión problemática en el pipeline para que nadie la vuelva a desplegar.
3. Abre un postmortem si el incidente fue SEV1 o SEV2.
