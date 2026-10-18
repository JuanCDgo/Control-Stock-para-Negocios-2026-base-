-- sql/dev/test_formato.sql — formato argentino en los mensajes que arma la base. SOLO local.
-- Uso: docker exec -i supabase_db_sb psql -U postgres -v ON_ERROR_STOP=1 < sql/dev/test_formato.sql

do $$
begin
    assert public.fmt_numero_ar(50000, 2) = '50.000,00', public.fmt_numero_ar(50000, 2);
    assert public.fmt_numero_ar(1234567.891, 2) = '1.234.567,89', public.fmt_numero_ar(1234567.891, 2);
    assert public.fmt_numero_ar(4.35, 3, true) = '4,35', public.fmt_numero_ar(4.35, 3, true);
    assert public.fmt_numero_ar(4, 3, true) = '4', public.fmt_numero_ar(4, 3, true);
    assert public.fmt_numero_ar(0.25, 3, true) = '0,25', public.fmt_numero_ar(0.25, 3, true);
end $$;

\echo 'test_formato: OK'
