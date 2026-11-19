---
servicio: auth-service
equipo: identidad
severidad: SEV1
fecha: 2026-10-09
actualizado: 2026-10-20
---
# Postmortem PM-2026-013: login caído por una rotación de clave JWT incompleta

## Resumen

El 9 de octubre, durante 28 minutos, ningún usuario pudo iniciar sesión y los que ya estaban dentro
fueron expulsados con el mensaje "sesión inválida". Severidad: SEV1.

## Causa raíz

La rotación programada de la clave de firma de los JWT publicó la clave nueva en auth-service, pero el
job que actualiza el JWKS falló. checkout-api y los demás servicios seguían validando los tokens con la
clave anterior, así que rechazaron todos los tokens nuevos con `invalid_signature`.

## Mitigación

Se volvió a publicar la clave anterior en el JWKS junto a la nueva. Los servicios aceptaron las dos
claves y el login se recuperó en dos minutos.

## Qué aprendimos

- Una rotación de claves tiene dos pasos que deben ir en orden: primero publicar la clave nueva en el
  JWKS, después empezar a firmar con ella.
- El error `invalid_signature` apareció en los logs de checkout-api, no en los de auth-service. Al
  principio buscamos el problema en el servicio equivocado.

## Acciones

- La rotación verifica que el JWKS ya tenga la clave nueva antes de usarla (hecho).
- Alerta sobre la tasa de `invalid_signature` en todos los servicios (pendiente).
