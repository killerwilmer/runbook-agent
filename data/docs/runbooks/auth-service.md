---
servicio: auth-service
equipo: identidad
actualizado: 2026-10-20
---
# Runbook: auth-service

auth-service maneja el login, el registro y la emisión de tokens JWT. Guarda las sesiones en Redis
(`redis-sessions`). Es un servicio crítico: si falla, los usuarios no pueden entrar ni comprar.

## El login falla para todos o para muchos usuarios

Revisa primero los logs de auth-service:

```bash
kubectl -n identidad logs deployment/auth-service --since=15m | grep -i error
```

- `invalid_signature` o `token signature verification failed`: la clave de firma de los JWT cambió o
  venció. Ve a la sección "Rotación de la clave JWT".
- `ERR_CONN_REFUSED redis-sessions:6379`: Redis no responde. Ve a la sección "Redis de sesiones".
- `rate limit exceeded`: puede ser un ataque de fuerza bruta. Avisa a seguridad antes de subir los
  límites.

## Rotación de la clave JWT

La clave de firma se rota cada 90 días. Si la rotación falla a medias, los tokens nuevos se firman
con una clave que los demás servicios todavía no conocen, y todos los usuarios ven "sesión inválida".

Mitigación: vuelve a publicar la clave anterior en el JWKS (`/.well-known/jwks.json`) para que se
acepten las dos claves mientras se completa la rotación. No borres la clave vieja hasta que hayan
pasado 24 horas.

## Redis de sesiones

Si Redis está caído, nadie puede iniciar sesión, pero los usuarios que ya tienen un token válido siguen
navegando. Revisa la memoria de Redis: con `maxmemory` lleno, Redis rechaza escrituras. Reiniciar Redis
cierra todas las sesiones activas, así que requiere aprobación del on-call de identidad.

## Escalamiento

Login caído para más del 50 % de los usuarios es SEV1. Fallas para un grupo pequeño (un navegador, un
país) suelen ser SEV2 o SEV3. Avisa al on-call del equipo de identidad.
