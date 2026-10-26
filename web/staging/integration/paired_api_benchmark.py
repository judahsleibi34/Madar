#!/usr/bin/env python3
"""Bounded randomized equal-hop comparison on the independently restored VM stack."""
import argparse
import json
from pathlib import Path

import manage
import independent_recovery as recovery

BASELINE='4f2c31aea7a10e33d337f506763258afa7e4419c'
CLIENT=r'''
from concurrent.futures import ThreadPoolExecutor
import json,math,random,sys,time
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
configuration=json.load(sys.stdin);opener=build_opener(ProxyHandler({}));result={}
for endpoint in ('/health/live','/auth/user_status','/admin/users'):
    runs=[]
    for pair in range(3):
        order=['baseline','candidate'];random.Random(148+pair).shuffle(order);row={'pair':pair,'order':order}
        for role in order:
            url='http://'+('baseline-api' if role=='baseline' else 'backend')+':8000'+endpoint
            headers={} if endpoint=='/health/live' else {'Cookie':configuration['cookie']}
            def fetch(_):
                started=time.perf_counter()
                try:
                    with opener.open(Request(url,headers=headers),timeout=15) as response:
                        payload=response.read();status=response.status
                        if endpoint=='/auth/user_status' and not json.loads(payload).get('logged_in'):status=401
                except HTTPError as error:status=error.code;error.close()
                except OSError:status=0
                return ((time.perf_counter()-started)*1000,status)
            for index in range(10):
                if fetch(index)[1]!=200:raise RuntimeError('Authenticated HTTP200 warmup required')
            started=time.perf_counter()
            with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(fetch,range(120)))
            elapsed=time.perf_counter()-started;ordered=sorted(v[0] for v in values)
            row[role]={'requests':120,'errors':sum(v[1]!=200 for v in values),'p50_ms':round(ordered[59],3),
                'p95_ms':round(ordered[math.ceil(len(ordered)*.95)-1],3),'throughput_rps':round(120/elapsed,3)}
        runs.append(row)
    result[endpoint]=runs
print(json.dumps(result,sort_keys=True))
'''


def main(mode):
    manage.require_staging_host()
    recovery.TARGET_PROJECT='madar-independent-recovery-20261017-attempt3'
    runtime=Path.home()/recovery.TARGET_PROJECT
    with recovery.target_context(runtime):
        state=manage.state();manage.attest_resources();manage.require_database_marker()
        acceptance=json.loads((runtime/'fresh-image-acceptance.json').read_text())
        if acceptance['source_overlay_used'] is not False or acceptance['schema']!=148:
            raise RuntimeError('Completed fresh image acceptance required')
        images=acceptance['images'];source=acceptance['source_sha']
        candidate_id=manage.compose('ps','-q','backend').decode().strip()
        candidate=json.loads(manage.docker('inspect',candidate_id))[0]
        if state['source_sha']!=source or candidate['Image']!=images['backend'] or not candidate['State']['Running']:
            raise RuntimeError('Candidate runtime changed after fresh acceptance')
        baseline='madar-hardening-application:'+BASELINE
        baseline_image=json.loads(manage.docker('image','inspect',baseline))[0]
        labels=baseline_image['Config'].get('Labels',{})
        if labels.get('com.madar.release.sha')!=BASELINE:raise RuntimeError('Baseline image identity changed')
        if mode=='INSPECT':
            print(json.dumps({'scope':'same synthetic restored cluster, equal direct HTTP hops','baseline':BASELINE,'candidate':source,'production_modified':False}));return
        if int(__import__('re').search(r'MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text()).group(1))<1300*1024:
            raise RuntimeError('Insufficient bounded benchmark memory headroom')
        if (runtime/'paired-benchmark.json').exists():raise RuntimeError('Preserve existing measured benchmark')
        if manage.docker('ps','-q','--filter','ancestor=madar-schema136-preparation-test:working').strip():
            raise RuntimeError('Wait for independent test load before benchmarking')
        if manage.docker('ps','-aq','--filter','label=com.docker.compose.project='+manage.PROJECT,'--filter','label=com.docker.compose.service=baseline-api').strip():
            raise RuntimeError('Preserve existing baseline service')
        service={'image':baseline,'pull_policy':'never','user':'65534:65534','read_only':True,'restart':'no',
            'networks':['isolated'],'labels':{'com.madar.staging.owner':manage.OWNER},'env_file':[str(runtime/'application.env')],
            'environment':{'MADAR_RELEASE_SHA':BASELINE},'tmpfs':['/tmp:rw,nosuid,nodev,size=256m,mode=1777'],
            'mem_limit':'768m','cpus':1.5,'pids_limit':256,'security_opt':['no-new-privileges:true'],'cap_drop':['ALL'],
            'healthcheck':{'test':['CMD','python','-c',"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health/live',timeout=2)"],
                'interval':'2s','timeout':'3s','retries':30},'logging':{'driver':'json-file','options':{'max-size':'2m','max-file':'2'}}}
        manage.private_write('paired-benchmark-compose.json',json.dumps({'services':{'baseline-api':service}}))
        def compose(*args):return manage.compose('--file',str(runtime/'fresh-compose.json'),'--file',str(runtime/'paired-benchmark-compose.json'),*args)
        def snapshot():
            answer={}
            for name in ('postgres','auth','backend','baseline-api'):
                identifier=compose('ps','-q',name).decode().strip()
                answer[name]=dict((key,int(value)) for key,value in (line.split() for line in manage.docker('exec',identifier,'cat','/sys/fs/cgroup/cpu.stat').decode().splitlines()))
            return answer
        def dataset():
            return json.loads(manage.sql("select json_build_object('users',(select count(*) from public.users),"
                "'tenants',(select count(*) from public.tenants),'projects',(select count(*) from public.builder_projects),"
                "'deliveries',(select count(*) from public.notification_deliveries));"))
        client_name=manage.PROJECT+'-paired-benchmark-client'
        if manage.docker('ps','-aq','--filter','name=^/'+client_name+'$').strip():
            raise RuntimeError('Preserve existing benchmark client')
        try:
            compose('up','--no-deps','-d','--wait','--wait-timeout','90','baseline-api')
            fixture=json.loads((runtime/'smoke-fixture.json').read_text())
            cookie='; '.join(key+'='+value for key,value in fixture['cookies'].items())
            before=snapshot();dataset_before=dataset()
            output=manage.docker('run','--rm','--name',client_name,'--label','com.madar.staging.owner='+manage.OWNER,
                '--network',manage.PROJECT+'_isolated','--read-only','--user','65534:65534',
                '--memory','96m','--cpus','.5','--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges:true',
                '--interactive','--entrypoint','python',images['backend'],'-c',CLIENT,
                data=json.dumps({'cookie':cookie}).encode(),timeout=600)
            measured=json.loads(output);after=snapshot()
            dataset_after=dataset()
            if dataset_after!=dataset_before:raise RuntimeError('Synthetic dataset changed during benchmark')
            report={'baseline_sha':BASELINE,'candidate_sha':source,'schema':148,'endpoints':measured,
                'baseline_image_id':baseline_image['Id'],'candidate_image_id':images['backend'],
                'dataset_before':dataset_before,'dataset_after':dataset_after,
                'conditions':{'warmups_per_run':10,'requests_per_run':120,'clients':2,'randomized_pairs':3,'seed':148,
                    'api_memory_mib':768,'api_cpus':1.5,'client_cpus':.5,'same_cluster_network_and_direct_hops':True},
                'cpu_stat_delta':{name:{key:after[name][key]-before[name][key] for key in ('usage_usec','nr_periods','nr_throttled','throttled_usec')} for name in before},
                'production_modified':False,'limitations':['small synthetic read workload','no p99 or production capacity claim',
                    'three pairs cannot establish a general speedup','no application optimization in this continuation','baseline overlay versus fresh build']}
            if any(run[role]['errors'] for runs in measured.values() for run in runs for role in ('baseline','candidate')):
                raise RuntimeError('Benchmark HTTP errors; do not claim performance acceptance')
            manage.private_write('paired-benchmark.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,sort_keys=True))
        finally:
            identifier=manage.docker('ps','-aq','--filter','name=^/'+client_name+'$').decode().strip()
            if identifier:
                row=json.loads(manage.docker('inspect',identifier))[0]
                if row['Image']!=images['backend'] or row['Config'].get('Labels',{}).get('com.madar.staging.owner')!=manage.OWNER:
                    raise RuntimeError('Unexpected benchmark client ownership; preserve it')
                manage.docker('rm','--force',identifier)
            compose('stop','--timeout','15','baseline-api');compose('rm','--force','baseline-api')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',nargs='?',default='INSPECT',choices=('INSPECT','REHEARSE'))
    main(parser.parse_args().mode)
