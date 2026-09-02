import csv,json
from tools.summarize_kvzap_route_a318_contract_breach import parse_args,run
H=('bank_count','burst_bytes','bank_bytes_per_cycle','pending_layout','staging_capacity_tokens_per_layer')
def gate(root,name,short_held):
 d=root/name;d.mkdir(); workloads={w:{'request_id':w,'lifecycle_dir':f'l/{w}','deferred_memory_dir':f'm/{w}','lifecycle_manifest_sha256':'x','memory_manifest_sha256':'y','memory_summary_sha256':'z'} for w in ('short','long')}
 (d/'contract_policy_sweep_manifest.json').write_text(json.dumps({'schema_version':'kvzap-route-a317-contract-policy-sweep-1.0','workloads':workloads}))
 fields=['workload','request_id','required_minimum_continuation_calls','deferred_decode_steps','admission_flush_token_budget',*H,'gate_path','net_bytes_saved_fraction','net_cycle_proxy_saved_fraction']
 rows=[]
 for w,cycle,path in [('short',0 if short_held else -0.2,'full_kv_no_admission' if short_held else 'active_deferred_admission'),('long',0.3,'active_deferred_admission')]:rows.append({'workload':w,'request_id':w,'required_minimum_continuation_calls':32,'deferred_decode_steps':0,'admission_flush_token_budget':512,**dict(zip(H,[16,64,64,'round_robin_token',8192])),'gate_path':path,'net_bytes_saved_fraction':0.0,'net_cycle_proxy_saved_fraction':cycle})
 with (d/'contract_policy_sweep_per_workload.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 cf=['required_minimum_continuation_calls','deferred_decode_steps','admission_flush_token_budget',*H,'all_workloads_nonnegative_cycle','active_workload_count','min_net_cycle_proxy_saved_fraction','mean_net_cycle_proxy_saved_fraction']
 with (d/'contract_policy_sweep_cross_summary.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=cf);w.writeheader();w.writerow({'required_minimum_continuation_calls':32,'deferred_decode_steps':0,'admission_flush_token_budget':512,**dict(zip(H,[16,64,64,'round_robin_token',8192])),'all_workloads_nonnegative_cycle':short_held,'active_workload_count':1 if short_held else 2,'min_net_cycle_proxy_saved_fraction':0 if short_held else -0.2,'mean_net_cycle_proxy_saved_fraction':0.15 if short_held else 0.05})
 with (d/'continuation_contract_audit.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['workload','contract_held_by_observed_trace']);w.writeheader();w.writerows([{'workload':'short','contract_held_by_observed_trace':short_held},{'workload':'long','contract_held_by_observed_trace':True}])
 return d
def test_breach_comparison_reports_negative_delta(tmp_path):
 h,b=gate(tmp_path,'honest',True),gate(tmp_path,'breach',False)
 per,cross,_=run(parse_args(['--honest-gate-dir',str(h),'--breach-gate-dir',str(b),'--breach-workload','short','--output-dir',str(tmp_path/'out')]))
 assert cross[0]['breach_all_workloads_nonnegative_cycle']=='False'
 assert cross[0]['breach_minus_honest_min_cycle_fraction']==-0.2
 assert [r for r in per if r['workload']=='short'][0]['breach_minus_honest_cycle_fraction']==-0.2
