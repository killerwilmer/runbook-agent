---
servicio: checkout-api
equipo: checkout
severidad: SEV1
fecha: 2026-08-14
actualizado: 2026-08-20
---
# Postmortem PM-2026-007: checkout-api caído por OOMKilled después de un deploy

## Resumen

El 14 de agosto, entre las 18:10 y las 18:52, el 70 % de los intentos de compra fallaron con 502. Los
pods de checkout-api entraron en CrashLoopBackOff por `OOMKilled` después del deploy de la versión
2.12.0. Duración: 42 minutos. Severidad: SEV1.

## Línea de tiempo

- 18:05 Deploy de checkout-api 2.12.0.
- 18:10 Se dispara `HighErrorRate checkout-api 5xx > 5%`.
- 18:18 El on-call ve pods reiniciándose con `OOMKilled` y escala a 5 réplicas. No ayuda: los pods
  nuevos también se quedan sin memoria.
- 18:40 Se decide hacer rollback a 2.11.3.
- 18:52 La tasa de errores vuelve a lo normal.

## Causa raíz

La versión 2.12.0 agregó una caché en memoria de las promociones activas sin límite de tamaño. Con el
tráfico de la tarde, la caché creció hasta superar el límite de 2Gi del contenedor.

## Qué aprendimos

- Escalar réplicas no sirve cuando cada pod se queda sin memoria por sí solo: solo multiplica los
  pods que fallan.
- Perdimos 22 minutos antes de hacer rollback. Ahora la regla es: si el incidente empezó después de un
  deploy, el rollback es la primera opción.

## Acciones

- Límite de tamaño para todas las cachés en memoria (hecho).
- Alerta de memoria al 80 % del límite del contenedor (hecho).
- Prueba de carga obligatoria antes de desplegar cambios en checkout-api (pendiente).
