---
servicio: checkout-api
equipo: checkout
actualizado: 2026-10-12
---
# Runbook: checkout-api

checkout-api arma el carrito, calcula el total y llama a payments-api para cobrar. Es un servicio
crítico: si falla, nadie puede comprar. Corre en Kubernetes (namespace `checkout`, 3 réplicas) con un
límite de memoria de 2Gi por pod.

## Síntomas frecuentes

- Los usuarios ven "Error al procesar tu compra" o una página en blanco al pagar.
- El balanceador devuelve 502 Bad Gateway o 504 Gateway Timeout.
- La alerta `HighErrorRate checkout-api 5xx > 5%` se dispara en el canal #alertas-prod.
- La latencia p99 supera los 2 segundos (lo normal es 300 a 500 ms).

## Diagnóstico

Primero revisa el estado de los pods:

```bash
kubectl -n checkout get pods -l app=checkout-api
kubectl -n checkout describe pod <pod>
```

Si un pod está en `CrashLoopBackOff`, mira la razón del último reinicio en `describe`. La causa más
común es `OOMKilled`: el contenedor superó su límite de memoria y Kubernetes lo terminó.

Después revisa si hubo un deploy reciente. En el historial de incidentes, la mayoría de las caídas de
checkout-api empezaron en los 30 minutos siguientes a un deploy:

```bash
kubectl -n checkout rollout history deployment/checkout-api
```

Si los pods están sanos pero hay errores 502, revisa la conexión con payments-api. Un timeout de
payments-api se ve en los logs de checkout-api como `upstream timeout payments-api`.

## Mitigación

1. **Si el problema empezó después de un deploy**, haz rollback a la versión anterior (ver el runbook
   de rollback). Es la mitigación más rápida: no intentes arreglar el código en caliente.
2. **Si hay pods en OOMKilled sin un deploy reciente**, escala temporalmente a 5 réplicas para repartir
   la carga mientras investigas:
   `kubectl -n checkout scale deployment/checkout-api --replicas=5`
3. **Si payments-api no responde**, el problema no está en checkout-api: sigue el runbook de
   payments-api y avisa al equipo de pagos.

Reiniciar pods sin entender la causa solo esconde el problema por unos minutos. Antes de reiniciar,
guarda los logs del pod que falló con `kubectl logs <pod> --previous`.

## Escalamiento

Errores 5xx por encima del 5 % durante más de 5 minutos son SEV1 o SEV2 según el porcentaje de usuarios
afectados. Avisa al on-call del equipo de checkout y abre el canal del incidente según la guía de
escalamiento.
