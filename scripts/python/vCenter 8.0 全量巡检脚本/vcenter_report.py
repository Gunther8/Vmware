#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vCenter 8.0 全量巡检报告 v2.0
功能：资源概览 / VM变更对比 / 健康告警 / 资源浪费 / 存储分析 / 趋势图
依赖：pip install pyVmomi requests
"""
import os, ssl, atexit, datetime, sqlite3, json, math
import requests
from pyVim import connect
from pyVmomi import vim

# ═══════════════════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════════════════
VCENTER_HOST     = "1.1.1.1"
VCENTER_USER     = "administrator@vsphere.local"
VCENTER_PASSWORD = "666666"
VCENTER_PORT     = 443

WECOM_KEY        = "123456"
WECOM_SEND_URL   = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={WECOM_KEY}"
WECOM_UPLOAD_URL = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={WECOM_KEY}&type=file"

SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
DB_PATH          = os.path.join(SCRIPT_DIR, "vcenter_history.db")

OLD_SNAPSHOT_DAYS        = 7
LONG_POWEROFF_DAYS       = 30
ZOMBIE_CPU_MHZ           = 100
ZOMBIE_MEM_PCT           = 10
OLD_HW_VER_NUM           = 14
OVERSIZED_MIN_VCPU       = 8
OVERSIZED_MIN_MEM_GB     = 16.0
OVERSIZED_CPU_PER_CORE   = 50
OVERSIZED_MEM_PCT        = 20

# ═══════════════════════════════════════════════════════
#  连接 vCenter
# ═══════════════════════════════════════════════════════
def connect_vcenter():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    si = connect.SmartConnect(
        host=VCENTER_HOST, user=VCENTER_USER, pwd=VCENTER_PASSWORD,
        port=VCENTER_PORT, sslContext=ctx)
    atexit.register(connect.Disconnect, si)
    return si

def get_all_objects(content, vimtype):
    c = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    objs = list(c.view)
    c.Destroy()
    return objs

# ═══════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════
def b2gb(b):   return b / (1024 ** 3)
def mb2gb(mb): return mb / 1024.0
def pct(u, t): return round(u / t * 100, 1) if t > 0 else 0.0
def is_nfs(ds): return ds.summary.type.lower() in ("nfs", "nfs41")

def fmt_gb(v):
    return f"{v/1024:.1f} TB" if v >= 1024 else f"{v:.1f} GB"

def util_color(v):
    return "#f44336" if v >= 85 else "#FF9800" if v >= 70 else "#4CAF50"

def bar(v):
    c = util_color(v)
    return (f'<div class="bar-wrap"><div class="bar" style="width:{min(v,100)}%;'
            f'background:{c}"></div><span class="bar-txt">{v}%</span></div>')

def oversell_ratio(threads, vcpu):
    return f"{vcpu/threads:.1f}:1" if threads > 0 else "-"

def hw_num(s):
    try:    return int(str(s).replace("vmx-", ""))
    except: return 99

TOOLS_LABEL = {
    "toolsOk":               ("正常",     "#4CAF50"),
    "toolsOld":              ("版本过旧",  "#FF9800"),
    "toolsNotRunning":       ("未运行",    "#f44336"),
    "toolsNotInstalled":     ("未安装",    "#f44336"),
    "guestToolsBlacklisted": ("已禁用",    "#9E9E9E"),
}

# ═══════════════════════════════════════════════════════
#  数据库
# ═══════════════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS vm_snapshots (
        snapshot_date     TEXT NOT NULL,
        vm_moid           TEXT NOT NULL,
        vm_name           TEXT NOT NULL,
        cluster           TEXT,
        power_state       TEXT,
        num_vcpu          INTEGER,
        memory_gb         REAL,
        disk_gb           REAL,
        ip_address        TEXT,
        guest_os          TEXT,
        host_name         TEXT,
        tools_status      TEXT,
        hw_version        TEXT,
        conn_state        TEXT,
        cpu_usage_mhz     INTEGER,
        mem_usage_mb      INTEGER,
        snap_count        INTEGER,
        snap_max_age_days INTEGER,
        PRIMARY KEY (snapshot_date, vm_moid)
    );
    CREATE TABLE IF NOT EXISTS ds_snapshots (
        snapshot_date TEXT NOT NULL,
        ds_moid       TEXT NOT NULL,
        ds_name       TEXT NOT NULL,
        ds_type       TEXT,
        cluster       TEXT,
        capacity_gb   REAL,
        used_gb       REAL,
        PRIMARY KEY (snapshot_date, ds_moid)
    );
    CREATE TABLE IF NOT EXISTS cluster_snapshots (
        snapshot_date TEXT NOT NULL,
        cluster_name  TEXT NOT NULL,
        cpu_pct       REAL,
        mem_pct       REAL,
        stor_pct      REAL,
        vm_total      INTEGER,
        vm_on         INTEGER,
        PRIMARY KEY (snapshot_date, cluster_name)
    );
    CREATE INDEX IF NOT EXISTS idx_vm_date  ON vm_snapshots(snapshot_date);
    CREATE INDEX IF NOT EXISTS idx_ds_date  ON ds_snapshots(snapshot_date);
    CREATE INDEX IF NOT EXISTS idx_cl_date  ON cluster_snapshots(snapshot_date);
    """)
    conn.commit()
    return conn

def save_snapshot(conn, today, all_vms, cluster_stats, all_ds):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vm_snapshots WHERE snapshot_date=?", (today,))
    if cur.fetchone()[0] > 0:
        print(f"  今日({today})快照已存在，跳过写库")
        return
    conn.executemany(
        "INSERT OR REPLACE INTO vm_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(today, v['moid'], v['name'], v['cluster'], v['power'], v['vcpu'],
          v['mem_gb'], v['disk_gb'], v['ip'], v['os'], v['host'],
          v['tools_status'], v['hw_version'], v['conn_state'],
          v['cpu_mhz'], v['mem_usage_mb'], v['snap_count'], v['snap_max_age_days'])
         for v in all_vms])
    conn.executemany(
        "INSERT OR REPLACE INTO ds_snapshots VALUES(?,?,?,?,?,?,?)",
        [(today, d['moid'], d['name'], d['type'], d['cluster'],
          d['capacity_gb'], d['used_gb']) for d in all_ds])
    conn.executemany(
        "INSERT OR REPLACE INTO cluster_snapshots VALUES(?,?,?,?,?,?,?)",
        [(today, c['name'], c['cpu_pct'], c['mem_pct'], c['stor_pct'],
          c['vm_total'], c['vm_on']) for c in cluster_stats])
    conn.commit()
    print(f"  写库完成：{len(all_vms)} 台VM，{len(all_ds)} 个数据存储")

def load_vm_snapshot(conn, date):
    cur = conn.cursor()
    cur.execute("""SELECT vm_moid,vm_name,cluster,power_state,num_vcpu,memory_gb,
        disk_gb,ip_address,guest_os,hw_version,tools_status,conn_state,
        cpu_usage_mhz,mem_usage_mb,snap_count,snap_max_age_days
        FROM vm_snapshots WHERE snapshot_date=?""", (date,))
    keys = ['moid','name','cluster','power','vcpu','mem_gb','disk_gb','ip','os',
            'hw_version','tools_status','conn_state','cpu_mhz','mem_usage_mb',
            'snap_count','snap_max_age_days']
    return [dict(zip(keys, r)) for r in cur.fetchall()]

def get_all_dates(conn):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT snapshot_date FROM vm_snapshots ORDER BY snapshot_date DESC")
    return [r[0] for r in cur.fetchall()]

def get_cluster_history(conn, days=30):
    cur = conn.cursor()
    cur.execute("""SELECT cluster_name,snapshot_date,cpu_pct,mem_pct,stor_pct,vm_total
        FROM cluster_snapshots WHERE snapshot_date>=date('now',?)
        ORDER BY cluster_name,snapshot_date""", (f'-{days} days',))
    res = {}
    for cl, dt, cpu, mem, stor, vmt in cur.fetchall():
        res.setdefault(cl, []).append({'date':dt,'cpu':cpu,'mem':mem,'stor':stor,'vm':vmt})
    return res

def get_ds_history(conn, days=60):
    cur = conn.cursor()
    cur.execute("""SELECT ds_name,snapshot_date,capacity_gb,used_gb
        FROM ds_snapshots WHERE snapshot_date>=date('now',?)
        ORDER BY ds_name,snapshot_date""", (f'-{days} days',))
    res = {}
    for name, dt, cap, used in cur.fetchall():
        res.setdefault(name, []).append({'date':dt,'capacity_gb':cap,'used_gb':used})
    return res

def get_long_poweroff(conn, today):
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT snapshot_date FROM vm_snapshots
        WHERE snapshot_date<=? ORDER BY snapshot_date DESC LIMIT ?""",
        (today, LONG_POWEROFF_DAYS + 5))
    dates = [r[0] for r in cur.fetchall()]
    if len(dates) < 2:
        return []
    cur.execute("SELECT vm_moid,vm_name,cluster FROM vm_snapshots WHERE snapshot_date=? AND power_state='off'",
        (today,))
    off_today = {r[0]: {'name': r[1], 'cluster': r[2]} for r in cur.fetchall()}
    if not off_today:
        return []
    ph_m = ','.join('?'*len(off_today))
    ph_d = ','.join('?'*len(dates))
    cur.execute(f"SELECT vm_moid,snapshot_date,power_state FROM vm_snapshots "
                f"WHERE vm_moid IN ({ph_m}) AND snapshot_date IN ({ph_d})",
                list(off_today) + dates)
    recs = {}
    for moid, dt, pw in cur.fetchall():
        recs.setdefault(moid, {})[dt] = pw
    result = []
    for moid, info in off_today.items():
        consecutive = 0
        for d in dates:
            if recs.get(moid, {}).get(d) == 'off':
                consecutive += 1
            else:
                break
        if consecutive >= LONG_POWEROFF_DAYS:
            result.append({**info, 'moid': moid, 'days_off': consecutive})
    return sorted(result, key=lambda x: x['days_off'], reverse=True)

def get_zombie_days(conn, moids, today):
    if not moids:
        return {}
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT snapshot_date FROM vm_snapshots
        WHERE snapshot_date<=? ORDER BY snapshot_date DESC LIMIT 30""", (today,))
    dates = [r[0] for r in cur.fetchall()]
    ph = ','.join('?'*len(moids)); ph_d = ','.join('?'*len(dates))
    cur.execute(f"SELECT vm_moid,snapshot_date,power_state,cpu_usage_mhz "
                f"FROM vm_snapshots WHERE vm_moid IN ({ph}) AND snapshot_date IN ({ph_d})",
                list(moids) + dates)
    recs = {}
    for moid, dt, pw, cpu in cur.fetchall():
        recs.setdefault(moid, {})[dt] = (pw, cpu or 0)
    result = {}
    for moid in moids:
        days = 0
        for d in dates:
            r = recs.get(moid, {}).get(d)
            if r and r[0] == 'on' and r[1] < ZOMBIE_CPU_MHZ:
                days += 1
            else:
                break
        result[moid] = max(days, 1)
    return result

# ═══════════════════════════════════════════════════════
#  数据采集
# ═══════════════════════════════════════════════════════
def get_snapshot_info(vm):
    if not vm.snapshot:
        return 0, 0
    count = max_age = 0
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    def walk(lst):
        nonlocal count, max_age
        for s in lst:
            count += 1
            age = (now - s.createTime).days
            if age > max_age:
                max_age = age
            walk(s.childSnapshotList)
    try:
        walk(vm.snapshot.rootSnapshotList)
    except Exception:
        pass
    return count, max_age

def get_vm_details(vm, cluster_name):
    try:
        if vm.config is None or vm.config.name.startswith("vCLS"):
            return None
        name   = vm.config.name
        power  = 'on' if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn else 'off'
        vcpu   = vm.config.hardware.numCPU
        mem_gb = round(vm.config.hardware.memoryMB / 1024, 2)
        disk_gb = 0.0
        for dev in (vm.config.hardware.device or []):
            if isinstance(dev, vim.vm.device.VirtualDisk):
                disk_gb += b2gb(dev.capacityInBytes or 0)
        disk_gb = round(disk_gb, 2)
        ip = ''
        if power == 'on' and vm.guest and vm.guest.ipAddress:
            ip = vm.guest.ipAddress
        os_name      = (vm.config.guestFullName or '').strip()
        hw_version   = vm.config.version or ''
        conn_state   = str(vm.runtime.connectionState)
        tools_status = str(vm.guest.toolsStatus or '') if vm.guest else ''
        cpu_mhz = mem_usage_mb = 0
        if power == 'on' and vm.summary.quickStats:
            cpu_mhz      = int(vm.summary.quickStats.overallCpuUsage or 0)
            mem_usage_mb = int(vm.summary.quickStats.guestMemoryUsage or 0)
        host_name = ''
        try:
            host_name = vm.runtime.host.name
        except Exception:
            pass
        snap_count, snap_max_age = get_snapshot_info(vm)
        return {
            'moid': vm._moId, 'name': name, 'cluster': cluster_name,
            'power': power, 'vcpu': vcpu, 'mem_gb': mem_gb, 'disk_gb': disk_gb,
            'ip': ip, 'os': os_name, 'host': host_name,
            'tools_status': tools_status, 'hw_version': hw_version,
            'conn_state': conn_state, 'cpu_mhz': cpu_mhz,
            'mem_usage_mb': mem_usage_mb,
            'snap_count': snap_count, 'snap_max_age_days': snap_max_age,
        }
    except Exception as e:
        print(f"    [警告] VM采集异常: {e}")
        return None

def collect_cluster(cluster):
    name = cluster.name
    total_cpu_cores = total_cpu_threads = host_count = 0
    total_cpu_mhz = used_cpu_mhz = total_mem_mb = used_mem_mb = 0.0
    for host in cluster.host:
        if host.runtime.connectionState != "connected":
            continue
        hw = host.hardware; qs = host.summary.quickStats
        total_cpu_cores   += hw.cpuInfo.numCpuCores
        total_cpu_threads += hw.cpuInfo.numCpuThreads
        total_cpu_mhz     += hw.cpuInfo.numCpuCores * hw.cpuInfo.hz / 1e6
        used_cpu_mhz      += qs.overallCpuUsage or 0
        total_mem_mb      += hw.memorySize / (1024 * 1024)
        used_mem_mb       += qs.overallMemoryUsage or 0
        host_count += 1
    seen_ds = set(); total_ds_b = used_ds_b = 0; all_ds = []
    for host in cluster.host:
        for ds in host.datastore:
            if ds._moId in seen_ds or is_nfs(ds):
                continue
            seen_ds.add(ds._moId)
            cap = ds.summary.capacity or 0; free = ds.summary.freeSpace or 0
            total_ds_b += cap; used_ds_b += cap - free
            all_ds.append({'moid': ds._moId, 'name': ds.summary.name,
                           'type': ds.summary.type, 'cluster': name,
                           'capacity_gb': round(b2gb(cap), 2),
                           'used_gb': round(b2gb(cap - free), 2)})
    alloc_vcpu = 0; alloc_mem_mb = alloc_stor_b = 0.0
    vm_total = vm_on = vm_off = 0
    seen_vm = set(); all_vms = []
    for host in cluster.host:
        for vm in host.vm:
            if vm._moId in seen_vm:
                continue
            seen_vm.add(vm._moId)
            det = get_vm_details(vm, name)
            if det is None:
                continue
            all_vms.append(det); vm_total += 1
            alloc_vcpu   += det['vcpu']
            alloc_mem_mb += det['mem_gb'] * 1024
            alloc_stor_b += det['disk_gb'] * (1024 ** 3)
            if det['power'] == 'on': vm_on += 1
            else:                    vm_off += 1
    stats = {
        'name': name, 'host_count': host_count,
        'total_cpu_cores': total_cpu_cores, 'total_cpu_threads': total_cpu_threads,
        'total_cpu_mhz': total_cpu_mhz, 'total_mem_gb': mb2gb(total_mem_mb),
        'total_stor_gb': b2gb(total_ds_b), 'alloc_vcpu': alloc_vcpu,
        'alloc_mem_gb': mb2gb(alloc_mem_mb), 'alloc_stor_gb': b2gb(alloc_stor_b),
        'used_cpu_mhz': used_cpu_mhz, 'used_mem_mb': used_mem_mb,
        'total_mem_mb': total_mem_mb, 'used_stor_gb': b2gb(used_ds_b),
        'cpu_pct': pct(used_cpu_mhz, total_cpu_mhz),
        'mem_pct': pct(used_mem_mb, total_mem_mb),
        'stor_pct': pct(b2gb(used_ds_b), b2gb(total_ds_b)),
        'vm_total': vm_total, 'vm_on': vm_on, 'vm_off': vm_off,
    }
    return stats, all_vms, all_ds

def aggregate(cs_list):
    def s(k): return sum(c[k] for c in cs_list)
    tc = s('total_cpu_mhz'); uc = s('used_cpu_mhz')
    tm = s('total_mem_mb');  um = s('used_mem_mb')
    ts = s('total_stor_gb'); us = s('used_stor_gb')
    return {
        'host_count': s('host_count'),
        'total_cpu_cores': s('total_cpu_cores'),
        'total_cpu_threads': s('total_cpu_threads'),
        'total_mem_gb': s('total_mem_gb'), 'total_stor_gb': ts,
        'alloc_vcpu': s('alloc_vcpu'), 'alloc_mem_gb': s('alloc_mem_gb'),
        'alloc_stor_gb': s('alloc_stor_gb'),
        'used_cpu_mhz': uc, 'used_mem_mb': um, 'used_stor_gb': us,
        'cpu_pct': pct(uc, tc), 'mem_pct': pct(um, tm), 'stor_pct': pct(us, ts),
        'vm_total': s('vm_total'), 'vm_on': s('vm_on'), 'vm_off': s('vm_off'),
    }

# ═══════════════════════════════════════════════════════
#  分析函数
# ═══════════════════════════════════════════════════════
def compute_diff(today_vms, compare_vms):
    td = {v['moid']: v for v in today_vms}
    cd = {v['moid']: v for v in compare_vms}
    def slim(v):
        return {'name':v['name'],'cluster':v['cluster'],'vcpu':v['vcpu'],
                'mem_gb':v['mem_gb'],'disk_gb':v['disk_gb'],
                'ip':v.get('ip',''),'os':v.get('os',''),'power':v.get('power','')}
    added   = [slim(v) for m, v in td.items() if m not in cd]
    removed = [slim(v) for m, v in cd.items() if m not in td]
    changed = []
    for moid in td:
        if moid in cd:
            t, c = td[moid], cd[moid]
            diffs = {}
            for f, lbl in [('vcpu','vCPU'),('mem_gb','内存GB'),('disk_gb','磁盘GB')]:
                if abs((t[f] or 0) - (c[f] or 0)) > 0.01:
                    diffs[lbl] = {'from': c[f], 'to': t[f]}
            if diffs:
                changed.append({'name':t['name'],'cluster':t['cluster'],
                                 'ip':t.get('ip',''),'changes':diffs})
    return {'added': added, 'removed': removed, 'changed': changed}

def build_all_diffs(conn, today, today_vms):
    dates = [d for d in get_all_dates(conn) if d != today]
    diffs = {}
    for date in dates:
        diffs[date] = compute_diff(today_vms, load_vm_snapshot(conn, date))
    return diffs, dates

def analyze_health(all_vms, conn, today):
    return {
        'old_snaps': sorted([v for v in all_vms if v['snap_count'] > 0 and
                              v['snap_max_age_days'] >= OLD_SNAPSHOT_DAYS],
                            key=lambda x: x['snap_max_age_days'], reverse=True),
        'problem':   [v for v in all_vms if v['conn_state'] in
                      ('orphaned', 'inaccessible', 'invalid')],
        'tools_issues': [v for v in all_vms if v['power'] == 'on' and
                         v['tools_status'] in ('toolsNotInstalled','toolsNotRunning',
                                               'toolsOld','guestToolsBlacklisted')],
        'old_hw':    sorted([v for v in all_vms if hw_num(v['hw_version']) < OLD_HW_VER_NUM],
                            key=lambda x: hw_num(x['hw_version'])),
        'long_off':  get_long_poweroff(conn, today),
    }

def analyze_waste(all_vms, conn, today):
    on_vms = [v for v in all_vms if v['power'] == 'on']
    zombies_raw = []
    for v in on_vms:
        mp = pct(v['mem_usage_mb'], v['mem_gb'] * 1024)
        if v['cpu_mhz'] < ZOMBIE_CPU_MHZ and mp < ZOMBIE_MEM_PCT:
            zombies_raw.append({**v, 'mem_live_pct': mp})
    zdays = get_zombie_days(conn, [v['moid'] for v in zombies_raw], today)
    zombies = sorted([{**v, 'idle_days': zdays.get(v['moid'], 1)} for v in zombies_raw],
                     key=lambda x: x['idle_days'], reverse=True)
    oversized = []
    for v in on_vms:
        mp  = pct(v['mem_usage_mb'], v['mem_gb'] * 1024)
        oc  = v['vcpu'] >= OVERSIZED_MIN_VCPU and v['cpu_mhz'] < v['vcpu'] * OVERSIZED_CPU_PER_CORE
        om  = v['mem_gb'] >= OVERSIZED_MIN_MEM_GB and mp < OVERSIZED_MEM_PCT
        if oc or om:
            oversized.append({**v, 'mem_live_pct': mp, 'over_cpu': oc, 'over_mem': om})
    oversized.sort(key=lambda x: x['mem_gb'] + x['vcpu'], reverse=True)
    return {'zombies': zombies, 'oversized': oversized}

def predict_fullness(history):
    if len(history) < 3:
        return None
    base = datetime.date.fromisoformat(history[0]['date'])
    xs = [(datetime.date.fromisoformat(h['date']) - base).days for h in history]
    ys = [h['used_gb'] for h in history]
    n = len(xs); xm = sum(xs)/n; ym = sum(ys)/n
    denom = sum((x - xm)**2 for x in xs)
    if denom == 0:
        return None
    slope = sum((x - xm)*(y - ym) for x, y in zip(xs, ys)) / denom
    if slope <= 0:
        return None
    return max(0, round((history[-1]['capacity_gb'] - history[-1]['used_gb']) / slope))

def analyze_storage(all_ds, conn):
    ds_hist = get_ds_history(conn, days=60)
    result = []
    for ds in all_ds:
        hist = ds_hist.get(ds['name'], [])
        result.append({**ds,
            'used_pct': pct(ds['used_gb'], ds['capacity_gb']),
            'days_left': predict_fullness(hist) if len(hist) >= 3 else None})
    return sorted(result, key=lambda x: x['used_pct'], reverse=True)

# ═══════════════════════════════════════════════════════
#  企业微信
# ═══════════════════════════════════════════════════════
def _wtag(v):
    if v >= 85: return f'<font color="warning">**{v}%** ⚠️</font>'
    if v >= 70: return f'<font color="warning">**{v}%**</font>'
    return f'<font color="info">**{v}%**</font>'

def send_wecom_markdown(overall, cluster_stats, health, waste, ts, fname):
    o = overall
    h_items = (
        ([f'过期快照 **{len(health["old_snaps"])}台**'] if health['old_snaps'] else []) +
        ([f'长期关机 **{len(health["long_off"])}台**']  if health['long_off']  else []) +
        ([f'Tools异常 **{len(health["tools_issues"])}台**'] if health['tools_issues'] else []) +
        ([f'孤立VM **{len(health["problem"])}台**']    if health['problem']   else [])
    )
    w_items = (
        ([f'僵尸VM **{len(waste["zombies"])}台**']   if waste['zombies']   else []) +
        ([f'超配VM **{len(waste["oversized"])}台**'] if waste['oversized'] else [])
    )
    lines = [
        "## vCenter 8.0 全量巡检报告 v2.0",
        f"> 巡检时间：**{ts}**　|　{VCENTER_HOST}", "",
        f"**CPU** 核心 **{o['total_cpu_cores']}** | 线程 **{o['total_cpu_threads']}** | vCPU **{o['alloc_vcpu']}** | 超售 **{oversell_ratio(o['total_cpu_threads'],o['alloc_vcpu'])}** | 使用率 {_wtag(o['cpu_pct'])}",
        f"**内存** {fmt_gb(o['total_mem_gb'])} | 已分配 {fmt_gb(o['alloc_mem_gb'])} | 使用率 {_wtag(o['mem_pct'])}",
        f"**存储** {fmt_gb(o['total_stor_gb'])} | 已分配 {fmt_gb(o['alloc_stor_gb'])} | 使用率 {_wtag(o['stor_pct'])}",
        f'**VM** 总 **{o["vm_total"]}** | <font color="info">开机 **{o["vm_on"]}**</font> | <font color="comment">关机 **{o["vm_off"]}**</font>',
    ]
    if h_items: lines.append(f'\n> ⚠️ 健康告警：{" | ".join(h_items)}')
    if w_items: lines.append(f'> ⚠️ 资源浪费：{" | ".join(w_items)}')
    lines += ["", "**各集群 VM（开机/总数）：**"]
    for c in cluster_stats:
        lines.append(f"> {c['name']}：{c['vm_on']}/{c['vm_total']}")
    lines.append(f'\n> 详细报告见附件 `{os.path.basename(fname)}`')
    payload = {"msgtype": "markdown", "markdown": {"content": "\n".join(lines)}}
    try:
        r = requests.post(WECOM_SEND_URL, json=payload, timeout=15)
        print("企微Markdown " + ("成功" if r.json().get("errcode")==0 else f'失败:{r.json()}'))
    except Exception as e:
        print(f"企微Markdown异常: {e}")

def send_wecom_file(fpath):
    try:
        with open(fpath, "rb") as f:
            r = requests.post(WECOM_UPLOAD_URL,
                files={"media": (os.path.basename(fpath), f, "text/html")}, timeout=30)
        mid = r.json().get("media_id")
        if not mid:
            print(f"企微上传失败: {r.json()}"); return
        r2 = requests.post(WECOM_SEND_URL,
            json={"msgtype":"file","file":{"media_id":mid}}, timeout=15)
        print("企微附件 " + ("成功" if r2.json().get("errcode")==0 else f'失败:{r2.json()}'))
    except Exception as e:
        print(f"企微文件异常: {e}")

# ═══════════════════════════════════════════════════════
#  HTML 生成
# ═══════════════════════════════════════════════════════
def _badge(power):
    return ('<span class="badge-on">开机</span>' if power == 'on'
            else '<span class="badge-off">关机</span>')

def _ok_row(colspan, msg="✅ 无异常"):
    return f'<tr><td colspan="{colspan}" class="ok-row">{msg}</td></tr>'

def _sec(sid, title, body, badge=None):
    badge_html = f' <span class="sec-badge">{badge}</span>' if badge else ''
    return f'''<div class="sec" id="{sid}">
  <div class="sec-hdr">{title}{badge_html}</div>
  <div class="sec-body">{body}</div>
</div>'''

def _table(headers, rows, empty_msg=None, empty_colspan=None):
    ths = "".join(f"<th>{h}</th>" for h in headers)
    body = rows if rows else _ok_row(empty_colspan or len(headers), empty_msg or "✅ 无数据")
    return f'<table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>'

# ── 各 Section ──────────────────────────────────────────
def _sec_overview(o):
    def card(cls, title, metrics):
        items = "".join(f'<div class="kv"><div class="val">{v}</div><div class="lbl">{l}</div></div>'
                        for v, l in metrics)
        return f'<div class="card {cls}"><div class="card-title">{title}</div><div class="card-body">{items}</div></div>'
    return f'''<div class="cards">
{card("cpu","CPU 资源",[
  (o['total_cpu_cores'], "物理核心"),
  (o['total_cpu_threads'], "逻辑处理器"),
  (o['alloc_vcpu'], "已分配vCPU"),
  (oversell_ratio(o['total_cpu_threads'],o['alloc_vcpu']), "超售比"),
  (f'<span style="color:{util_color(o["cpu_pct"])}">{o["cpu_pct"]}%</span>',"实际使用率")])}
{card("mem","内存资源",[
  (fmt_gb(o['total_mem_gb']), "物理内存"),
  (fmt_gb(o['alloc_mem_gb']), "已分配"),
  (f'<span style="color:{util_color(o["mem_pct"])}">{o["mem_pct"]}%</span>',"实际使用率")])}
{card("stor","存储资源 (vSAN+FC，不含NFS)",[
  (fmt_gb(o['total_stor_gb']), "总容量"),
  (fmt_gb(o['alloc_stor_gb']), "已分配"),
  (f'<span style="color:{util_color(o["stor_pct"])}">{o["stor_pct"]}%</span>',"实际使用率")])}
</div>'''

def _sec_cluster(cluster_stats, o):
    def row(c):
        return (f'<tr><td><b>{c["name"]}</b></td>'
                f'<td class="n">{c["host_count"]}</td>'
                f'<td class="n">{c["total_cpu_cores"]}</td>'
                f'<td class="n">{c["total_cpu_threads"]}</td>'
                f'<td class="n">{fmt_gb(c["total_mem_gb"])}</td>'
                f'<td class="n">{fmt_gb(c["total_stor_gb"])}</td>'
                f'<td class="n">{c["alloc_vcpu"]}</td>'
                f'<td class="n">{oversell_ratio(c["total_cpu_threads"],c["alloc_vcpu"])}</td>'
                f'<td class="n">{fmt_gb(c["alloc_mem_gb"])}</td>'
                f'<td class="n">{fmt_gb(c["alloc_stor_gb"])}</td>'
                f'<td>{bar(c["cpu_pct"])}</td>'
                f'<td>{bar(c["mem_pct"])}</td>'
                f'<td>{bar(c["stor_pct"])}</td></tr>')
    ttl = (f'<tr class="ttl"><td>汇总</td>'
           f'<td class="n">{o["host_count"]}</td>'
           f'<td class="n">{o["total_cpu_cores"]}</td>'
           f'<td class="n">{o["total_cpu_threads"]}</td>'
           f'<td class="n">{fmt_gb(o["total_mem_gb"])}</td>'
           f'<td class="n">{fmt_gb(o["total_stor_gb"])}</td>'
           f'<td class="n">{o["alloc_vcpu"]}</td>'
           f'<td class="n">{oversell_ratio(o["total_cpu_threads"],o["alloc_vcpu"])}</td>'
           f'<td class="n">{fmt_gb(o["alloc_mem_gb"])}</td>'
           f'<td class="n">{fmt_gb(o["alloc_stor_gb"])}</td>'
           f'<td>{bar(o["cpu_pct"])}</td>'
           f'<td>{bar(o["mem_pct"])}</td>'
           f'<td>{bar(o["stor_pct"])}</td></tr>')
    rows = "".join(row(c) for c in cluster_stats) + ttl
    hdrs = ["集群名称","主机数","物理核心","逻辑处理器","物理内存","存储容量",
            "已分配vCPU","超售比","已分配内存","已分配存储","CPU使用率","内存使用率","存储使用率"]
    body = _table(hdrs, rows)
    return _sec("sec-cluster", f"集群资源详情（共 {len(cluster_stats)} 个集群）", body)

def _sec_vm_table(cluster_stats, o):
    def row(c):
        return (f'<tr><td><b>{c["name"]}</b></td>'
                f'<td class="n">{c["vm_total"]}</td>'
                f'<td class="n on">{c["vm_on"]}</td>'
                f'<td class="n off">{c["vm_off"]}</td></tr>')
    ttl = (f'<tr class="ttl"><td>汇总</td>'
           f'<td class="n">{o["vm_total"]}</td>'
           f'<td class="n on">{o["vm_on"]}</td>'
           f'<td class="n off">{o["vm_off"]}</td></tr>')
    rows = "".join(row(c) for c in cluster_stats) + ttl
    body = _table(["集群名称","VM总数","开机","关机"], rows)
    return _sec("sec-vm", "虚拟机统计", body)

def _sec_diff(compare_dates):
    if not compare_dates:
        inner = '<div class="empty-tip">📅 暂无历史数据，明日起可进行变更对比</div>'
    else:
        inner = '''<div class="diff-toolbar">
  <label>对比日期：</label>
  <select id="diff-select" onchange="showDiff()">
    <option value="">── 请选择 ──</option>
  </select>
  <span id="diff-summary" style="margin-left:16px;color:#666;font-size:13px"></span>
</div>
<div id="diff-result"></div>'''
    return _sec("sec-diff", "VM 变更记录", inner)

def _sec_health(health):
    tabs = [
        ("快照告警",   f'{len(health["old_snaps"])}' if health['old_snaps'] else ''),
        ("长期关机",   f'{len(health["long_off"])}' if health['long_off'] else ''),
        ("Tools 异常", f'{len(health["tools_issues"])}' if health['tools_issues'] else ''),
        ("旧硬件版本", f'{len(health["old_hw"])}' if health['old_hw'] else ''),
        ("孤立/异常",  f'{len(health["problem"])}' if health['problem'] else ''),
    ]
    tab_headers = "".join(
        f'<div class="tab{" active" if i==0 else ""}" onclick="switchTab(this,\'tab{i}\')">'
        f'{name}{"<span class=\'tab-badge\'>"+cnt+"</span>" if cnt else ""}</div>'
        for i, (name, cnt) in enumerate(tabs))

    def snap_rows():
        rows = "".join(
            f'<tr><td>{v["name"]}</td><td>{v["cluster"]}</td>'
            f'<td class="n warn">{v["snap_count"]}</td>'
            f'<td class="n warn">{v["snap_max_age_days"]} 天</td>'
            f'<td>{_badge(v["power"])}</td></tr>'
            for v in health['old_snaps'])
        return _table(["VM名称","集群","快照数","最老快照","状态"], rows,
                      f"✅ 无超过 {OLD_SNAPSHOT_DAYS} 天的快照")

    def off_rows():
        rows = "".join(
            f'<tr><td>{v["name"]}</td><td>{v["cluster"]}</td>'
            f'<td class="n warn">{v["days_off"]} 天</td></tr>'
            for v in health['long_off'])
        return _table(["VM名称","集群","连续关机天数"], rows,
                      f"✅ 无连续关机超过 {LONG_POWEROFF_DAYS} 天的VM")

    def tools_rows():
        rows = "".join(
            f'<tr><td>{v["name"]}</td><td>{v["cluster"]}</td>'
            f'<td>{v["ip"] or "-"}</td>'
            f'<td style="color:{TOOLS_LABEL.get(v["tools_status"],("-","#999"))[1]}">'
            f'{TOOLS_LABEL.get(v["tools_status"],("未知","#999"))[0]}</td></tr>'
            for v in health['tools_issues'])
        return _table(["VM名称","集群","IP","Tools状态"], rows, "✅ 所有在线VM的Tools状态正常")

    def hw_rows():
        rows = "".join(
            f'<tr><td>{v["name"]}</td><td>{v["cluster"]}</td>'
            f'<td class="n warn">{v["hw_version"]}</td>'
            f'<td>{_badge(v["power"])}</td></tr>'
            for v in health['old_hw'])
        return _table(["VM名称","集群","硬件版本","状态"], rows,
                      f"✅ 无低于 vmx-{OLD_HW_VER_NUM} 的VM")

    def orphan_rows():
        rows = "".join(
            f'<tr><td>{v["name"]}</td><td>{v["cluster"]}</td>'
            f'<td class="n warn">{v["conn_state"]}</td></tr>'
            for v in health['problem'])
        return _table(["VM名称","集群","连接状态"], rows, "✅ 无孤立或异常VM")

    total = sum(len(health[k]) for k in ['old_snaps','long_off','tools_issues','old_hw','problem'])
    panes = "".join(
        f'<div id="tab{i}" class="tab-pane{" active" if i==0 else ""}">{content}</div>'
        for i, content in enumerate([snap_rows(), off_rows(), tools_rows(), hw_rows(), orphan_rows()]))
    body = f'<div class="tabs">{tab_headers}</div><div class="tab-content">{panes}</div>'
    return _sec("sec-health", "VM 健康告警", body,
                badge=str(total) if total else None)

def _sec_waste(waste):
    z_rows = "".join(
        f'<tr><td>{v["name"]}</td><td>{v["cluster"]}</td>'
        f'<td class="n">{v["vcpu"]}</td><td class="n">{v["mem_gb"]} GB</td>'
        f'<td class="n warn">{v["cpu_mhz"]} MHz</td>'
        f'<td class="n warn">{v["mem_live_pct"]}%</td>'
        f'<td class="n">{v["idle_days"]} 天</td></tr>'
        for v in waste['zombies'])
    z_table = _table(["VM名称","集群","配置vCPU","配置内存",
                       "CPU用量","内存使用率","持续低利用"], z_rows,
                      "✅ 无疑似僵尸VM")

    o_rows = "".join(
        f'<tr><td>{v["name"]}</td><td>{v["cluster"]}</td>'
        f'<td class="n">{v["vcpu"]}</td><td class="n">{v["mem_gb"]} GB</td>'
        f'<td class="n warn">{v["cpu_mhz"]} MHz</td>'
        f'<td class="n warn">{v["mem_live_pct"]}%</td>'
        f'<td>{"CPU " if v["over_cpu"] else ""}{"内存" if v["over_mem"] else ""}</td></tr>'
        for v in waste['oversized'])
    o_table = _table(["VM名称","集群","配置vCPU","配置内存",
                       "CPU用量","内存使用率","超配维度"], o_rows,
                      "✅ 无明显超配VM")

    total = len(waste['zombies']) + len(waste['oversized'])
    body = (f'<div class="sub-title">疑似僵尸VM（开机但 CPU &lt; {ZOMBIE_CPU_MHZ}MHz 且内存使用 &lt; {ZOMBIE_MEM_PCT}%）</div>'
            f'{z_table}'
            f'<div class="sub-title" style="margin-top:20px">疑似超配VM（开机但资源大量闲置）</div>'
            f'{o_table}')
    return _sec("sec-waste", "资源浪费分析", body,
                badge=str(total) if total else None)

def _sec_storage(storage_analysis):
    def days_cell(d):
        if d is None:
            return '<span style="color:#999">数据积累中</span>'
        if d < 30:
            return f'<span style="color:#f44336;font-weight:bold">{d} 天后写满 ⚠️</span>'
        if d < 90:
            return f'<span style="color:#FF9800">{d} 天后写满</span>'
        return f'<span style="color:#4CAF50">{d} 天后写满</span>'

    rows = "".join(
        f'<tr><td>{s["name"]}</td><td class="n">{s["type"]}</td>'
        f'<td>{s["cluster"]}</td>'
        f'<td class="n">{fmt_gb(s["capacity_gb"])}</td>'
        f'<td class="n">{fmt_gb(s["used_gb"])}</td>'
        f'<td>{bar(s["used_pct"])}</td>'
        f'<td class="n">{days_cell(s["days_left"])}</td></tr>'
        for s in storage_analysis)
    body = _table(["数据存储","类型","集群","总容量","已用","使用率","增长预测"], rows)
    return _sec("sec-stor", "存储深度分析", body)

def _sec_trends(has_trend):
    if not has_trend:
        return ''
    body = '''<div class="chart-grid">
  <div class="chart-box"><div class="chart-label">CPU 使用率趋势</div><canvas id="chart-cpu"></canvas></div>
  <div class="chart-box"><div class="chart-label">内存使用率趋势</div><canvas id="chart-mem"></canvas></div>
  <div class="chart-box"><div class="chart-label">存储使用率趋势</div><canvas id="chart-stor"></canvas></div>
  <div class="chart-box"><div class="chart-label">VM 数量趋势</div><canvas id="chart-vm"></canvas></div>
</div>'''
    return _sec("sec-trend", "资源趋势图（近 30 天）", body)

# ── CSS ─────────────────────────────────────────────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Microsoft YaHei",Arial,sans-serif;background:#f0f2f5;color:#333;font-size:14px}
a{text-decoration:none}

.hdr{background:linear-gradient(135deg,#0d2b4e,#1976D2);color:#fff;padding:26px 40px}
.hdr h1{font-size:24px;margin-bottom:6px}
.hdr p{opacity:.8;font-size:13px}

nav{position:sticky;top:0;z-index:100;background:#0d2b4e;display:flex;gap:2px;padding:0 20px;box-shadow:0 2px 8px rgba(0,0,0,.3)}
nav a{color:#cdd8e8;padding:12px 14px;font-size:13px;white-space:nowrap;transition:background .2s}
nav a:hover,nav a.active{background:#1976D2;color:#fff}

.wrap{max-width:1700px;margin:22px auto;padding:0 20px}

.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-bottom:20px}
.card{background:#fff;border-radius:8px;padding:18px 20px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.card-title{font-size:12px;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;padding-left:8px;border-left:4px solid #ccc}
.card.cpu .card-title{border-color:#2196F3}.card.mem .card-title{border-color:#4CAF50}.card.stor .card-title{border-color:#FF9800}
.card-body{display:flex;flex-wrap:wrap;gap:10px 16px}
.kv .val{font-size:20px;font-weight:700;color:#0d2b4e}.kv .lbl{font-size:11px;color:#999;margin-top:2px}

.sec{background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:20px;overflow:hidden}
.sec-hdr{background:#0d2b4e;color:#fff;padding:12px 22px;font-size:15px;font-weight:600;display:flex;align-items:center;gap:10px}
.sec-badge{background:#f44336;color:#fff;border-radius:10px;padding:1px 8px;font-size:12px}
.sec-body{padding:0}

table{width:100%;border-collapse:collapse}
th{background:#f5f7fa;color:#555;font-weight:600;padding:10px 13px;text-align:left;border-bottom:2px solid #e0e0e0;white-space:nowrap;font-size:13px}
td{padding:9px 13px;border-bottom:1px solid #f0f0f0;font-size:13px;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fafbfe}
.n{text-align:center}
.on{color:#388E3C;font-weight:700}.off{color:#D32F2F;font-weight:700}
.warn{color:#E65100;font-weight:600}
.ttl{background:#e3f2fd!important;font-weight:700}
.ttl td{border-top:2px solid #2196F3}
.ok-row{text-align:center;padding:18px;color:#4CAF50;font-style:italic}

.bar-wrap{position:relative;background:#e8ecef;border-radius:20px;height:20px;min-width:100px;overflow:hidden}
.bar{height:100%;border-radius:20px}
.bar-txt{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:11px;font-weight:700;color:#333;white-space:nowrap}

.badge-on{background:#E8F5E9;color:#388E3C;border-radius:4px;padding:2px 7px;font-size:12px;font-weight:600}
.badge-off{background:#FFEBEE;color:#D32F2F;border-radius:4px;padding:2px 7px;font-size:12px;font-weight:600}

.tabs{display:flex;border-bottom:2px solid #e0e0e0;padding:0 16px;background:#fafbfc}
.tab{padding:10px 16px;cursor:pointer;color:#666;font-size:13px;font-weight:600;border-bottom:3px solid transparent;margin-bottom:-2px;transition:all .2s;white-space:nowrap;display:flex;align-items:center;gap:6px}
.tab.active{color:#1976D2;border-bottom-color:#1976D2}
.tab:hover{color:#1976D2}
.tab-badge{background:#f44336;color:#fff;border-radius:10px;padding:0 6px;font-size:11px;min-width:18px;text-align:center}
.tab-content{padding:0}
.tab-pane{display:none}.tab-pane.active{display:block}

.sub-title{padding:14px 20px 8px;font-weight:600;color:#0d2b4e;font-size:14px;border-top:1px solid #f0f0f0}
.sub-title:first-child{border-top:none}

.diff-toolbar{padding:16px 20px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #f0f0f0;flex-wrap:wrap}
.diff-toolbar select{padding:6px 10px;border:1px solid #d0d0d0;border-radius:4px;font-size:13px;min-width:160px}
.diff-toolbar button{padding:6px 16px;background:#1976D2;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px}
.diff-toolbar button:hover{background:#1565C0}
#diff-result{padding:0}
.diff-section-title{padding:12px 20px 6px;font-weight:600;font-size:13px;border-top:1px solid #f0f0f0}
.diff-section-title:first-child{border-top:none}
.empty-tip{padding:40px;text-align:center;color:#999;font-style:italic}

.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:20px}
.chart-box{background:#fafbfc;border-radius:6px;padding:16px;border:1px solid #f0f0f0}
.chart-label{font-weight:600;color:#0d2b4e;margin-bottom:10px;font-size:13px}

.foot{text-align:center;color:#aaa;font-size:12px;padding:18px 0 28px}
"""

# ── JS ──────────────────────────────────────────────────
def _js(js_diffs, js_dates, js_history, has_trend):
    charts_code = ""
    if has_trend:
        charts_code = """
const COLORS=['#2196F3','#4CAF50','#FF9800','#f44336','#9C27B0','#00BCD4','#8BC34A','#FF5722'];
function mkChart(id, label, key){
  const clusters=Object.keys(clusterHistory);
  if(!clusters.length)return;
  const allDates=[...new Set(clusters.flatMap(cl=>clusterHistory[cl].map(d=>d.date)))].sort();
  const datasets=clusters.map((cl,i)=>({
    label:cl,borderColor:COLORS[i%COLORS.length],backgroundColor:'transparent',
    borderWidth:2,pointRadius:3,tension:0.3,
    data:allDates.map(d=>{const r=clusterHistory[cl].find(x=>x.date===d);return r?r[key]:null})
  }));
  new Chart(document.getElementById(id),{type:'line',data:{labels:allDates,datasets},
    options:{responsive:true,plugins:{legend:{position:'bottom',labels:{boxWidth:12,font:{size:11}}}},
      scales:{x:{ticks:{font:{size:10},maxRotation:45}},
              y:{min:0,max:key==='vm'?undefined:100,
                 ticks:{callback:(v)=>key==='vm'?v:v+'%'}}}}});
}
mkChart('chart-cpu','CPU使用率','cpu');
mkChart('chart-mem','内存使用率','mem');
mkChart('chart-stor','存储使用率','stor');
mkChart('chart-vm','VM数量','vm');
"""
    return f"""<script>
const vmDiffs={js_diffs};
const availDates={js_dates};
const clusterHistory={js_history};

// 填充日期下拉框
(function(){{
  const sel=document.getElementById('diff-select');
  if(!sel)return;
  availDates.forEach(d=>{{const o=document.createElement('option');o.value=d;o.text=d;sel.appendChild(o);}});
  if(availDates.length>0){{sel.value=availDates[0];showDiff();}}
}})();

function showDiff(){{
  const date=document.getElementById('diff-select').value;
  const result=document.getElementById('diff-result');
  const summary=document.getElementById('diff-summary');
  if(!date||!vmDiffs[date]){{result.innerHTML='';summary.textContent='';return;}}
  const d=vmDiffs[date];
  summary.textContent=`新增 ${{d.added.length}} 台 · 消失 ${{d.removed.length}} 台 · 变更 ${{d.changed.length}} 台`;
  let html='';
  html+=diffTable('✅ 新增 VM（'+d.added.length+'台）',
    ['VM名称','集群','vCPU','内存','磁盘','IP','系统','状态'],
    d.added.map(v=>`<tr><td>${{v.name}}</td><td>${{v.cluster}}</td>`+
      `<td class="n">${{v.vcpu}}</td><td class="n">${{v.mem_gb}} GB</td>`+
      `<td class="n">${{v.disk_gb}} GB</td><td>${{v.ip||'-'}}</td>`+
      `<td>${{v.os||'-'}}</td><td>${{v.power==='on'?'<span class="badge-on">开机</span>':'<span class="badge-off">关机</span>'}}</td></tr>`).join(''),
    '#E8F5E9','#388E3C');
  html+=diffTable('❌ 消失 VM（'+d.removed.length+'台）',
    ['VM名称','集群','vCPU','内存','磁盘','IP','系统'],
    d.removed.map(v=>`<tr><td>${{v.name}}</td><td>${{v.cluster}}</td>`+
      `<td class="n">${{v.vcpu}}</td><td class="n">${{v.mem_gb}} GB</td>`+
      `<td class="n">${{v.disk_gb}} GB</td><td>${{v.ip||'-'}}</td><td>${{v.os||'-'}}</td></tr>`).join(''),
    '#FFEBEE','#D32F2F');
  html+=diffTable('🔧 配置变更 VM（'+d.changed.length+'台）',
    ['VM名称','集群','IP','变更内容'],
    d.changed.map(v=>{{
      const items=Object.entries(v.changes).map(([k,c])=>`${{k}}: ${{c.from}} → ${{c.to}}`).join(' | ');
      return `<tr><td>${{v.name}}</td><td>${{v.cluster}}</td><td>${{v.ip||'-'}}</td><td class="warn">${{items}}</td></tr>`;
    }}).join(''),
    '#FFF8E1','#E65100');
  result.innerHTML=html;
}}

function diffTable(title,headers,rows,bgColor,titleColor){{
  const ths=headers.map(h=>`<th>${{h}}</th>`).join('');
  const body=rows||`<tr><td colspan="${{headers.length}}" class="ok-row">无</td></tr>`;
  return `<div class="diff-section-title" style="color:${{titleColor}}">${{title}}</div>`+
    `<table><thead><tr>${{ths}}</tr></thead><tbody>${{body}}</tbody></table>`;
}}

function switchTab(el,paneId){{
  el.parentElement.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  el.closest('.sec-body').querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
  document.getElementById(paneId).classList.add('active');
}}

// 导航高亮
window.addEventListener('scroll',()=>{{
  const secs=document.querySelectorAll('.sec[id]');
  let cur='';
  secs.forEach(s=>{{if(s.getBoundingClientRect().top<=80)cur=s.id;}});
  document.querySelectorAll('nav a').forEach(a=>{{
    a.classList.toggle('active',a.getAttribute('href')==='#'+cur);
  }});
}});

{charts_code}
</script>"""

# ── 主构建函数 ────────────────────────────────────────────
def build_html(overall, cluster_stats, all_diffs, compare_dates,
               health, waste, storage_analysis, cluster_history, today_str, ts):
    o = overall
    js_diffs   = json.dumps(all_diffs,        ensure_ascii=False)
    js_dates   = json.dumps(compare_dates,    ensure_ascii=False)
    js_history = json.dumps(cluster_history,  ensure_ascii=False)
    has_trend  = any(len(v) >= 7 for v in cluster_history.values())

    nav_items = [
        ("#sec-cluster","集群资源"), ("#sec-vm","VM统计"),
        ("#sec-diff","变更记录"),   ("#sec-health","健康告警"),
        ("#sec-waste","资源浪费"),  ("#sec-stor","存储分析"),
    ]
    if has_trend:
        nav_items.append(("#sec-trend","趋势图"))
    nav_html = "".join(f'<a href="{href}">{label}</a>' for href, label in nav_items)

    health_total = sum(len(health[k]) for k in ['old_snaps','long_off','tools_issues','old_hw','problem'])
    waste_total  = len(waste['zombies']) + len(waste['oversized'])

    chart_src = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>' if has_trend else ''

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>vCenter 巡检报告 {today_str}</title>
{chart_src}
<style>{CSS}</style>
</head>
<body>
<div class="hdr">
  <h1>vCenter 8.0 全量巡检报告</h1>
  <p>vCenter：{VCENTER_HOST} &nbsp;|&nbsp; 报告日期：{today_str} &nbsp;|&nbsp; 生成时间：{ts}</p>
</div>
<nav>{nav_html}</nav>
<div class="wrap">
{_sec_overview(o)}
{_sec_cluster(cluster_stats, o)}
{_sec_vm_table(cluster_stats, o)}
{_sec_diff(compare_dates)}
{_sec_health(health)}
{_sec_waste(waste)}
{_sec_storage(storage_analysis)}
{_sec_trends(has_trend)}
</div>
<div class="foot">报告生成时间：{ts} &nbsp;|&nbsp; vCenter 8.0 全量巡检 &nbsp;|&nbsp; {VCENTER_HOST}</div>
{_js(js_diffs, js_dates, js_history, has_trend)}
</body>
</html>"""

# ═══════════════════════════════════════════════════════
#  主程序
# ═══════════════════════════════════════════════════════
def main():
    print(f"连接 vCenter {VCENTER_HOST} ...")
    si = connect_vcenter()
    content = si.RetrieveContent()
    print("连接成功\n")

    clusters = get_all_objects(content, [vim.ClusterComputeResource])
    print(f"发现 {len(clusters)} 个集群：")
    for c in clusters:
        print(f"  · {c.name}")

    cluster_stats, all_vms, all_ds = [], [], []
    for cluster in clusters:
        print(f"\n  采集: {cluster.name}")
        stats, vms, ds = collect_cluster(cluster)
        cluster_stats.append(stats)
        all_vms.extend(vms)
        all_ds.extend(ds)
        print(f"    CPU {stats['total_cpu_cores']}核 {stats['cpu_pct']}% | "
              f"内存 {fmt_gb(stats['total_mem_gb'])} {stats['mem_pct']}% | "
              f"存储 {fmt_gb(stats['total_stor_gb'])} {stats['stor_pct']}%")
        print(f"    VM 总{stats['vm_total']} 开{stats['vm_on']} 关{stats['vm_off']}")

    cluster_stats.sort(key=lambda c: c['vm_total'], reverse=True)
    overall = aggregate(cluster_stats)

    print("\n  写入数据库...")
    conn = init_db()
    today = datetime.date.today().isoformat()
    save_snapshot(conn, today, all_vms, cluster_stats, all_ds)

    print("  分析数据...")
    all_diffs, compare_dates = build_all_diffs(conn, today, all_vms)
    health          = analyze_health(all_vms, conn, today)
    waste           = analyze_waste(all_vms, conn, today)
    storage_analysis = analyze_storage(all_ds, conn)
    cluster_history = get_cluster_history(conn, days=30)
    conn.close()

    ts    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fname = os.path.join(SCRIPT_DIR,
            f"vcenter_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

    print("  生成报告...")
    html = build_html(overall, cluster_stats, all_diffs, compare_dates,
                      health, waste, storage_analysis, cluster_history, today, ts)
    with open(fname, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n{'='*55}")
    print(f"报告：{fname}")
    print(f"VM总数：{overall['vm_total']}  开机：{overall['vm_on']}  关机：{overall['vm_off']}")
    print(f"健康告警：过期快照{len(health['old_snaps'])} | 长期关机{len(health['long_off'])} | "
          f"Tools异常{len(health['tools_issues'])} | 旧HW{len(health['old_hw'])} | 孤立{len(health['problem'])}")
    print(f"资源浪费：僵尸VM{len(waste['zombies'])} | 超配VM{len(waste['oversized'])}")
    print(f"历史对比：可与 {len(compare_dates)} 个历史日期对比")

    print("\n推送企业微信...")
    send_wecom_markdown(overall, cluster_stats, health, waste, ts, fname)
    send_wecom_file(fname)


if __name__ == "__main__":
    main()
