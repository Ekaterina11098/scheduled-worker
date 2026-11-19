create function public.china_advertising_report_state_v1(p_key text,p_payload jsonb,p_create boolean default false)
returns boolean language plpgsql security invoker
set search_path='' set statement_timeout='60s'
as $body$
declare changed integer;
begin
 if p_key !~ '^china_agent:advertising_(source|midday_source|artifacts|midday_artifacts):[0-9]{4}-[0-9]{2}-[0-9]{2}:[A-Za-z0-9_-]+$' then
  raise exception 'Key outside report-state scope' using errcode='22023';
 end if;
 if p_create then
  insert into public.telegram_api_cache(cache_key,payload,updated_at,expires_at)
  values(p_key,p_payload,now(),now()+interval '3650 days') on conflict(cache_key)do nothing;
 else
  update public.telegram_api_cache set payload=p_payload,updated_at=now() where cache_key=p_key;
 end if;
 get diagnostics changed=row_count;
 return changed=1;
end;$body$;
revoke all on function public.china_advertising_report_state_v1(text,jsonb,boolean) from public,anon,authenticated;
grant execute on function public.china_advertising_report_state_v1(text,jsonb,boolean) to service_role;
notify pgrst,'reload schema';