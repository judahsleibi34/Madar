"""Read-only proxy-instance and Nginx worker-generation observations."""
import re
from deployment.lib.emergency_routing_repair import spec

PROXY='madar-release-proxy'

def worker_snapshot(runtime):
    row=runtime.inspect([PROXY])[PROXY]
    if row['State']['Running'] is not True:
        raise RuntimeError('handoff_proxy_not_running')
    text=runtime.command(['docker','top',PROXY,'-eo','pid,args'])
    workers=set()
    for line in text.splitlines():
        match=re.fullmatch(r'\s*([0-9]+)\s+nginx: worker process(?: is shutting down)?\s*',line)
        if match:workers.add(int(match[1]))
    if not workers:raise RuntimeError('handoff_proxy_workers_missing')
    return {'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row),
        'started_at':row['State']['StartedAt'],'pid':row['State']['Pid'],'workers':sorted(workers)}

def previous_workers_drained(previous,current):
    if any(previous[key]!=current[key] for key in ('container_id','image_id','spec_sha256','started_at','pid')):
        raise RuntimeError('handoff_proxy_instance_changed')
    old=set(previous['workers']);new=set(current['workers'])
    return bool(new-old) and not bool(old&new)
