-- =====================================================================
-- Autenticación y roles (Dueño / Cajero)
--
-- Qué crea:
--   * Tabla  public.usuarios  (PIN guardado como HASH bcrypt, nunca en claro)
--   * 2 usuarios de ejemplo para comercio_id = 1:
--         Dueño  -> rol 'admin'  -> PIN 1234
--         Cajero -> rol 'cajero' -> PIN 0000
--   * RPC  listar_usuarios_login(p_comercio_id)       -> usuarios activos (sin hash)
--   * RPC  verificar_login(p_usuario_id, p_pin)       -> valida PIN con bloqueo anti fuerza bruta
--   * RPC  cambiar_pin(p_usuario_id, p_actual, p_nuevo)
--
-- Seguridad:
--   * RLS activado y SIN políticas + permisos revocados: ni anon ni authenticated pueden
--     leer/escribir la tabla directamente (el hash no sale de la base). Solo se accede por
--     las funciones SECURITY DEFINER de abajo.
--   * 5 PIN incorrectos seguidos -> el usuario se bloquea 5 minutos.
--   * Los PIN de ejemplo (1234 / 0000) son INSEGUROS: quien entre con uno de ellos recibe
--     debe_cambiar_pin = true y la app no lo deja seguir hasta elegir otro. cambiar_pin
--     tampoco acepta 1234 / 0000 como PIN nuevo.
--
-- NOTA: se asume comercios.id numérico (bigint/int). Ejecutar completo en el editor SQL.
-- =====================================================================

create extension if not exists pgcrypto with schema extensions;

-- ---------- Tabla ----------
create table if not exists public.usuarios (
    id                bigint generated always as identity primary key,
    comercio_id       bigint not null references public.comercios(id),
    nombre            text   not null,
    pin_hash          text   not null,                       -- bcrypt (crypt + gen_salt('bf'))
    rol               text   not null check (rol in ('admin', 'cajero')),
    activo            boolean not null default true,
    intentos_fallidos integer not null default 0,
    bloqueado_hasta   timestamptz,
    created_at        timestamptz not null default now(),
    constraint usuarios_nombre_unico unique (comercio_id, nombre)
);

-- Por si la tabla ya existía de antes: agrega las columnas de control que falten
alter table public.usuarios add column if not exists intentos_fallidos integer not null default 0;
alter table public.usuarios add column if not exists bloqueado_hasta   timestamptz;

-- ---------- Blindaje de acceso directo ----------
alter table public.usuarios enable row level security;
revoke all on table public.usuarios from anon, authenticated;

-- ---------- Usuarios iniciales (comercio_id = 1) ----------
insert into public.usuarios (comercio_id, nombre, pin_hash, rol)
values
    (1, 'Dueño',  extensions.crypt('1234', extensions.gen_salt('bf')), 'admin'),
    (1, 'Cajero', extensions.crypt('0000', extensions.gen_salt('bf')), 'cajero')
on conflict (comercio_id, nombre) do nothing;

-- ---------- RPC: listar usuarios para la pantalla de login ----------
create or replace function public.listar_usuarios_login(p_comercio_id bigint)
returns table (id bigint, nombre text, rol text)
language sql
security definer
set search_path = public
as $$
    select u.id, u.nombre, u.rol
      from usuarios u
     where u.comercio_id = p_comercio_id
       and u.activo
     order by (u.rol = 'admin') desc, u.nombre;
$$;

-- ---------- RPC: verificar PIN ----------
-- Devuelve jsonb (NO lanza excepción en PIN incorrecto: si lo hiciera, el rollback
-- desharía el incremento del contador de intentos).
--   ok=true : { ok, usuario: { id, nombre, rol, comercio_id, debe_cambiar_pin } }
--   ok=false: { ok, motivo: 'usuario_invalido' | 'bloqueado' | 'pin_incorrecto',
--               intentos_restantes?, minutos_bloqueo? }
create or replace function public.verificar_login(p_usuario_id bigint, p_pin text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_u        usuarios%rowtype;
    v_max      constant integer := 5;
    v_bloqueo  constant interval := interval '5 minutes';
    v_restan   integer;
begin
    select * into v_u from usuarios where id = p_usuario_id for update;

    if not found or not v_u.activo then
        return jsonb_build_object('ok', false, 'motivo', 'usuario_invalido');
    end if;

    if v_u.bloqueado_hasta is not null and v_u.bloqueado_hasta > now() then
        return jsonb_build_object(
            'ok', false, 'motivo', 'bloqueado',
            'minutos_bloqueo', ceil(extract(epoch from (v_u.bloqueado_hasta - now())) / 60)::int
        );
    end if;

    if p_pin is not null and v_u.pin_hash = extensions.crypt(p_pin, v_u.pin_hash) then
        update usuarios set intentos_fallidos = 0, bloqueado_hasta = null where id = v_u.id;
        return jsonb_build_object(
            'ok', true,
            'usuario', jsonb_build_object(
                'id', v_u.id, 'nombre', v_u.nombre, 'rol', v_u.rol, 'comercio_id', v_u.comercio_id,
                'debe_cambiar_pin', p_pin in ('1234', '0000')
            )
        );
    end if;

    -- PIN incorrecto: contar intento y bloquear al llegar al máximo
    if v_u.bloqueado_hasta is not null then          -- venía de un bloqueo ya vencido
        v_u.intentos_fallidos := 0;
    end if;
    v_u.intentos_fallidos := v_u.intentos_fallidos + 1;

    if v_u.intentos_fallidos >= v_max then
        update usuarios
           set intentos_fallidos = 0, bloqueado_hasta = now() + v_bloqueo
         where id = v_u.id;
        return jsonb_build_object('ok', false, 'motivo', 'bloqueado', 'minutos_bloqueo', 5);
    end if;

    update usuarios
       set intentos_fallidos = v_u.intentos_fallidos, bloqueado_hasta = null
     where id = v_u.id;
    v_restan := v_max - v_u.intentos_fallidos;
    return jsonb_build_object('ok', false, 'motivo', 'pin_incorrecto', 'intentos_restantes', v_restan);
end;
$$;

-- ---------- RPC: cambiar PIN (4 dígitos numéricos) ----------
-- Devuelve jsonb { ok, motivo? } con motivo: 'pin_invalido' | 'pin_inseguro' | 'pin_actual_incorrecto'
--                                            | 'usuario_invalido'
create or replace function public.cambiar_pin(p_usuario_id bigint, p_pin_actual text, p_pin_nuevo text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_u usuarios%rowtype;
begin
    if p_pin_nuevo is null or p_pin_nuevo !~ '^[0-9]{4}$' then
        return jsonb_build_object('ok', false, 'motivo', 'pin_invalido');
    end if;
    if p_pin_nuevo in ('1234', '0000') then
        return jsonb_build_object('ok', false, 'motivo', 'pin_inseguro');
    end if;

    select * into v_u from usuarios where id = p_usuario_id and activo for update;
    if not found then
        return jsonb_build_object('ok', false, 'motivo', 'usuario_invalido');
    end if;

    if p_pin_actual is null or v_u.pin_hash <> extensions.crypt(p_pin_actual, v_u.pin_hash) then
        return jsonb_build_object('ok', false, 'motivo', 'pin_actual_incorrecto');
    end if;

    update usuarios
       set pin_hash = extensions.crypt(p_pin_nuevo, extensions.gen_salt('bf'))
     where id = p_usuario_id;
    return jsonb_build_object('ok', true);
end;
$$;

-- ---------- Permisos de las funciones ----------
revoke all on function public.listar_usuarios_login(bigint)            from public;
revoke all on function public.verificar_login(bigint, text)            from public;
revoke all on function public.cambiar_pin(bigint, text, text)          from public;
grant execute on function public.listar_usuarios_login(bigint)         to anon, authenticated, service_role;
grant execute on function public.verificar_login(bigint, text)         to anon, authenticated, service_role;
grant execute on function public.cambiar_pin(bigint, text, text)       to anon, authenticated, service_role;

notify pgrst, 'reload schema';
