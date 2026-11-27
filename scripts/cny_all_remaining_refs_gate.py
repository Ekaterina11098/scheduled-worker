"""Continue only an unfinished, still-authorized reference-only operation."""
import os
import cny_all_remaining_refs_apply as a
db=a.m.Cache(a.b.ReadOnly());result=db.get(a.b.ROOT+a.P+'result:v1')
if result:
 assert result['status']=='verified';needed=False
else:
 auth=db.get(a.b.ROOT+a.P+'authorization:v1')
 assert auth and auth['authorized'] and auth['scope']=='remaining_ms_currency_references_only'
 needed=True
with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('continue='+str(needed).lower()+'\n')
print('Protected continuation readiness checked.')
