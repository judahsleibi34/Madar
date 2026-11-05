"""Bounded real Docker/systemd proxy lifecycle component; no release authority.

Runs only an owned network-none container and transient test unit. Reproduces
historical Compose-project name conflict, then uses the production drop-in's
exact-ID start/stop commands with its root gate and User=madar arrangement.
"""
from pathlib import Path
import datetime, hashlib, json, os, re, shutil, subprocess, sys, time, uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from deployment.lib.completed_normal_boot_installation import proxy_bytes

WORK=Path('/opt/madar-development')
IMAGE='sha256:3b7e1b0cd406712c50cfbc777c97a0188c9d0239b6a79c53a28862e4278b2dca'

def command(args,*,timeout=40,check=True):
    return subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=check)

def main():
    assert os.getuid()==1000 and Path.cwd().is_relative_to(WORK)
    assert shutil.disk_usage(WORK).free>10*1024**3
    available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    assert available>2*1024**3
    run='codex-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-proxy-boot-'+uuid.uuid4().hex[:8]
    root=WORK/'scratch/codex-runs'/run;evidence=WORK/'evidence/integration'/run
    root.mkdir(mode=0o700);evidence.mkdir(mode=0o700)
    unit='madar-test-'+run+'.service';name=run+'-proxy';identity=None;unit_created=False
    ledger={'run_id':run,'status':'FAIL','scope':'COMPONENT only: real Docker/project conflict and transient systemd lifecycle; no migration, production service or release authority','source_sha':command(['git','rev-parse','HEAD']).stdout.strip(),'source_file_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'installer_sha256':hashlib.sha256((Path(__file__).resolve().parents[2]/'deployment/lib/completed_normal_boot_installation.py').read_bytes()).hexdigest(),'image':IMAGE,'user':1000,'disk_free_before':shutil.disk_usage(WORK).free}
    def docker(*args,**kwargs):return command(['sudo','-n','docker',*args],**kwargs)
    try:
        assert docker('image','inspect',IMAGE).returncode==0
        manifest=root/'compose.json'
        manifest.write_text(json.dumps({'services':{'proxy':{'image':IMAGE,'container_name':name,
            'labels':{'com.madar.test.run':run},'network_mode':'none','read_only':True,
            'user':'1000:1000','cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],
            'mem_limit':'256m','cpus':1,'pids_limit':64,'restart':'no',
            'entrypoint':['/usr/bin/timeout','120s','python3','-B','-m','http.server','8080','--bind','127.0.0.1']}}}))
        manifest.chmod(0o600)
        docker('compose','-p',run.lower()+'-historical','-f',str(manifest),'create','proxy',timeout=60)
        row=json.loads(docker('inspect',name).stdout)[0];identity=row['Id']
        assert re.fullmatch('[a-f0-9]{64}',identity) and row['Image']==IMAGE
        assert row['Config']['Labels']['com.madar.test.run']==run and not row['State']['Running']
        conflict=docker('compose','-p',run.lower()+'-successor','-f',str(manifest),'create','proxy',check=False,timeout=60)
        assert conflict.returncode!=0 and 'already in use' in conflict.stderr
        ledger['different_project_refused']=True
        # This guard authenticates only the native fixture's owned container;
        # production continues using its existing installed root proxy gate.
        gate=root/'guard.py'
        gate.write_text('import json,os,subprocess\nassert os.geteuid()==0\nr=json.loads(subprocess.check_output(["/usr/bin/docker","inspect",'+repr(identity)+']))[0]\nassert r["Id"]=='+repr(identity)+' and r["Image"]=='+repr(IMAGE)+' and r["Config"]["Labels"]["com.madar.test.run"]=='+repr(run)+'\nassert r["HostConfig"]["NetworkMode"]=="none" and not r["State"]["Running"]\n')
        gate.chmod(0o400)
        dropin=proxy_bytes(unit,'/usr/bin/python3 -I -B '+str(gate),proxy_id=identity).decode()
        directives={key:[] for key in ('ExecStartPre','ExecStart','ExecStop')}
        for line in dropin.splitlines():
            key,sep,value=line.partition('=')
            if sep and key in directives:
                if value:directives[key].append(value)
                else:directives[key]=[]
        assert all(len(v)==1 for v in directives.values())
        start=directives['ExecStart'][0].split();stop=directives['ExecStop'][0]
        assert start==['/usr/bin/docker','start',identity]
        command(['sudo','-n','systemd-run','--unit='+unit,'--collect','--uid=madar','--gid=madar',
            '--property=Type=oneshot','--property=RemainAfterExit=yes','--property=RuntimeMaxSec=90',
            '--property=TimeoutStartSec=30','--property=TimeoutStopSec=30','--property=MemoryMax=256M',
            '--property=CPUQuota=100%','--property=NoNewPrivileges=yes',
            '--property=ExecStartPre='+directives['ExecStartPre'][0],'--property=ExecStop='+stop,*start])
        unit_created=True;deadline=time.monotonic()+35
        while True:
            state=command(['systemctl','show',unit,'-p','ActiveState','-p','SubState','-p','Result']).stdout
            if 'ActiveState=active' in state:break
            if 'ActiveState=failed' in state or time.monotonic()>deadline:raise RuntimeError('native_proxy_unit_start_failed')
            time.sleep(.2)
        effective=command(['systemctl','show',unit,'-p','ExecStart','-p','ExecStop']).stdout
        values=dict(line.split('=',1) for line in effective.splitlines() if '=' in line)
        for key in ('ExecStart','ExecStop'):
            value=values[key]
            assert value.count('argv[]=')==1 and 'argv[]='+directives[key][0]+' ;' in value and 'path=/usr/bin/docker ;' in value
        ledger['effective_commands_verified']=True
        row=json.loads(docker('inspect',identity).stdout)[0]
        assert row['Id']==identity and row['State']['Running'] and row['Image']==IMAGE
        health=docker('exec',identity,'python3','-c','from urllib.request import urlopen; assert urlopen("http://127.0.0.1:8080",timeout=5).status==200',timeout=15)
        assert health.returncode==0
        command(['sudo','-n','systemctl','stop',unit])
        assert not json.loads(docker('inspect',identity).stdout)[0]['State']['Running']
        ledger.update(status='COMPONENT_PASS',same_container_started=True,root_gate_before_madar_start=True,private_http_healthy=True,exact_id_stop_observed=True,container_id=identity)
    except BaseException as error:
        ledger['failure_type']=type(error).__name__
        diagnostic=(str(getattr(error,'stdout','') or '')+str(getattr(error,'stderr','') or ''))[-16384:]
        log=evidence/'private-failure.log';log.write_text(diagnostic);log.chmod(0o600)
        raise
    finally:
        if unit_created:
            command(['sudo','-n','systemctl','stop',unit],check=False)
            deadline=time.monotonic()+5
            while True:
                state=command(['systemctl','show',unit,'-p','LoadState','--value'],check=False).stdout.strip()
                if state=='not-found':break
                if time.monotonic()>deadline:raise RuntimeError('native_proxy_unit_not_retired')
                time.sleep(.1)
            ledger['transient_unit_retired']=True
        if identity:
            row=json.loads(docker('inspect',identity).stdout)[0]
            assert row['Config']['Labels']['com.madar.test.run']==run and row['Name']=='/'+name and row['Image']==IMAGE
            docker('rm','--force',identity)
            assert docker('inspect',identity,check=False).returncode!=0
        else:
            # A partial create may not be forgotten merely because no ID was read.
            rows=docker('ps','-aq','--filter','label=com.madar.test.run='+run).stdout.split()
            assert not rows,'native_proxy_partial_create_requires_owned_retirement'
        assert all(p.is_file() and not p.is_symlink() and p.stat().st_uid==os.getuid() for p in root.iterdir())
        shutil.rmtree(root)
        ledger.update(owned_resources_removed=True,disk_free_after=shutil.disk_usage(WORK).free)
        (evidence/'result.json').write_text(json.dumps(ledger,indent=2)+'\n')
        print(json.dumps(ledger))

if __name__=='__main__':main()
