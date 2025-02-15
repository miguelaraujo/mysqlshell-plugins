from numpy import size
import support.collections.common as common
common.collectList.append("metrics.collect")
common.plotList.append("metrics.plot")

def _get_flush_points(session):
    stmt = "select name, count from information_schema.INNODB_METRICS where name like 'log_max_%'"
    result = session.run_sql(stmt)
    rows = result.fetch_all()
    return int(rows[0][1]), int(rows[1][1])

def _get_async_flush_point(session):
    stmt = "select round((@@innodb_log_file_size * @@innodb_log_files_in_group) * (6/8))"
    result = session.run_sql(stmt)
    row = result.fetch_one()
    return int(row[0])

def _get_sync_flush_point(session):
    stmt = "select round((@@innodb_log_file_size * @@innodb_log_files_in_group) * (7/8))"
    result = session.run_sql(stmt)
    row = result.fetch_one()
    return int(row[0])

def _get_redo_log_capacity(session):
    stmt = "select @@innodb_redo_log_capacity"
    result = session.run_sql(stmt)
    row = result.fetch_one()
    return int(row[0])

def _get_sync_pct(x, var1, var2, var3):
    # we need to get the amount of sync utilization
    # we do: (check_point_age - async_flush_point) / (sync_flush_point - async_flush_point) * 100
    #        and if <0 it stays to 0
    if(x[var1]-x[var2]) > 0:
        x=round(((x[var1]-x[var2]) / (x[var3]-x[var2]))*100,2)
    else:
        x=0
    return x

def collect(session, header, minute_cpt):
    stmt = "select unix_timestamp() as `timestamp`, t1.* from sys.metrics as t1"
    common._run_me(session, stmt, header, "metrics.txt")
    return

def plot(session):
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as font_manager
    
    common._get_collected_info("{}/global_info.txt".format(common.outdir))

    data = pd.read_csv("{}/metrics.txt".format(common.outdir), sep='\t')
    #replacing high value by something
    #data=data.replace('18446744073709551615', '99')
    #removing high value metrics
    data=data[data.Variable_value != '18446744073709551615']

    # innodb_log_writes vs innodb_log_write_requests
    common._generate_graph("innodb_log.png", "InnoDB Log", data, [["innodb_log_writes"], ["innodb_log_write_requests"]])
    # innodb_buffer_pool_reads vs innodb_buffer_pool_read_requests
    common._generate_graph("innodb_reads.png", "InnoDB Reads", data, [["innodb_buffer_pool_reads"], ["innodb_buffer_pool_read_requests"]])
    # InnoDB Flushing (innodb_buffer_pool_pages_flushed)
    common._generate_graph("innodb_flushing.png", "InnoDB Flushing", data, [["innodb_buffer_pool_pages_flushed"]])
    # InnoDB OS Log Writes (innodb_os_log_written)
    common._generate_graph("innodb_os_log.png", "InnoDB OS Log Writes", data, [["innodb_os_log_written"]])
    # InnoDB Pending
    common._generate_graph("innodb_pending.png", "InnoDB Pending", data, [["innodb_data_pending_fsyncs",1], 
                                                                          ["innodb_data_pending_reads",1],
                                                                          ["innodb_data_pending_writes",1]])
    # Threads
    common._generate_graph("mysql_threads.png", "MySQL Threads", data, [["threads_cached",1], 
                                                                        ["threads_connected",1],
                                                                        ["threads_created"],
                                                                        ["threads_running",1]], "line")
    # MySQL Threads Running
    common._generate_graph("mysql_threads_running.png", "MySQL Threads Running", data, [["threads_running",1]])

    # Aborted connections
    common._generate_graph("mysql_aborted_connections.png", "MySQL Aborted Connections", data, [["aborted_clients"], 
                                                                        ["aborted_connects"], 
                                                                        ["mysqlx_aborted_clients"]])
    
    # Joins
    common._generate_graph("mysql_joins.png", "MySQL Joins", data, [["select_full_join"], 
                                                                        ["select_full_range_join"],
                                                                        ["select_range"],
                                                                        ["select_range_check"],
                                                                        ["select_scan"]], "line")
    
    # Sorting
    common._generate_graph("mysql_sorts.png", "MySQL Sorting", data, [["sort_merge_passes"], 
                                                                        ["sort_range"],
                                                                        ["sort_rows"],
                                                                        ["sort_scan"]], "line")

    # Temporary Tables
    common._generate_graph("mysql_tmp_tables.png", "MySQL Temporary Tables", data, [["created_tmp_disk_tables"], 
                                                                        ["created_tmp_tables"]], "area")

    # Handler Statistics
    common._generate_graph("mysql_handler_stats.png", "MySQL Handler Statistics", data, [["handler_delete"], 
                                                                        ["handler_read_first"],
                                                                        ["handler_read_key"],
                                                                        ["handler_read_last"],
                                                                        ["handler_read_prev"],
                                                                        ["handler_read_next"],
                                                                        ["handler_read_rnd"],
                                                                        ["handler_read_rnd_next"],
                                                                        ["handler_update"],
                                                                        ["handler_write"]], "line")

    # MySQL Queries
    common._generate_graph("mysql_queries.png", "MySQL Queries", data, [["queries"]], "area")  

    # InnoDB Inserts
    common._generate_graph("mysql_dml.png", "MySQL DML", data, [["dml_deletes"], 
                                                                ["dml_inserts"], 
                                                                ["dml_reads"], 
                                                                ["dml_system_deletes"], 
                                                                ["dml_system_inserts"], 
                                                                ["dml_system_reads"], 
                                                                ["dml_system_updates"], 
                                                                ["dml_updates"]], "area") 

    # Buffer Pool
    common._generate_graph("innodb_buffer_pool.png", "MySQL InnoDB Buffer Pool", data, [  
                                                                        ["innodb_buffer_pool_pages_data", 1], 
                                                                        ["innodb_buffer_pool_pages_misc", 1],
                                                                        ["innodb_buffer_pool_pages_free", 1]], "area", True)

    # Buffer Pool Dirty
    common._generate_graph("innodb_buffer_pool_dirty.png", "MySQL InnoDB Buffer Pool - Dirty Pages", data, [  
                                                                        ["innodb_buffer_pool_pages_data", 1], 
                                                                        ["innodb_buffer_pool_pages_dirty", 1]], "area", False)
   
    # History List Length
    common._generate_graph("mysql_history_list_length.png", "MySQL History List Length", data, [["trx_rseg_history_len",1]], "area", False)  

    # Checkpoint Age
    # Here we set the second element of the "variables" to 3, this means it's a
    # fix value
    major, middle, minor = common._get_version_info(common.collectedInfo['version'])
    if int(major) == 8 and int(minor) < 30:
        print("Redo Log < 8.0.30 detected")
        async_flush_point=_get_async_flush_point(session)
        sync_flush_point=_get_sync_flush_point(session)
        common._generate_graph("mysql_checkpoint.png", "MySQL Checkpoint Age", data, [["log_lsn_checkpoint_age",1], 
                                                                                    [async_flush_point,3,"async flush point"],
                                                                                    [sync_flush_point,3,"sync flush point"]
                                                                                    ], "line")  
    else:
        print("New Redo Log (>=8.0.30) detected")
        redo_log_capacity = _get_redo_log_capacity(session)
        async_flush_point, sync_flush_point = _get_flush_points(session)
        soft_logical_capacity = round(((async_flush_point * 8/7) + (sync_flush_point * 16/15)) / 2)
        hard_logical_capacity = round(redo_log_capacity * 29.8/32)

        common._generate_graph("mysql_checkpoint.png", "MySQL Checkpoint Age", data, [
                                                                                ["log_lsn_checkpoint_age",1],
                                                                                [redo_log_capacity,3,"redo log capacity"],
                                                                                [hard_logical_capacity,3,"hard logical capacity"],
                                                                                [soft_logical_capacity,3,"soft logical capacity"],
                                                                                [sync_flush_point,3,"sync flush point"],
                                                                                [async_flush_point,3,"async flush point"]
                                                                                ], "line" )
    common._generate_graph("mysql_checkpoint_lsn.png", "MySQL Checkpoint LSN Stacked (buffer / disk)", 
                           data, [["innodb_redo_log_flushed_to_disk_lsn",1],["innodb_redo_log_current_lsn",1]], "line" )
    common._generate_graph("mysql_checkpoint_lsn_diff.png", "MySQL Checkpoint LSN (buffer / disk)", 
                           data, [["innodb_redo_log_flushed_to_disk_lsn",0],["innodb_redo_log_current_lsn",0]], "line" )
    lsn_data_current = data[data['Variable_name'] == 'innodb_redo_log_current_lsn']
    lsn_data_current = lsn_data_current.astype({'Variable_value':'uint64'})    
    lsn_data_disk = data[data['Variable_name'] == 'innodb_redo_log_flushed_to_disk_lsn']
    lsn_data_disk = lsn_data_disk.astype({'Variable_value':'uint64'})   
    lsn_data_current['current_lsn'] = lsn_data_current['Variable_value']
    lsn_data_disk['flushed_to_disk_lsn'] = lsn_data_disk['Variable_value']
    lsn_data = lsn_data_current[['timestamp', 'current_lsn']].merge(lsn_data_disk[['timestamp','flushed_to_disk_lsn']])
    lsn_data['Variable_value']=lsn_data['current_lsn']-lsn_data['flushed_to_disk_lsn']
    lsn_data['Variable_name']='lsn_diff'
    common._generate_graph("mysql_checkpoint_lsn_diff.png", "MySQL Checkpoint LSN delay\n(difference between lsn_current and lsn_flushed_to_disk)", 
                           lsn_data, [["lsn_diff",1]], "line" )
    
    # Transaction Log
    # This metrics is special, so I do not use the generic one as we do some computation
    trx_log_data1 = data[data['Variable_name'] == 'log_lsn_checkpoint_age']
    trx_log_data1 = trx_log_data1.astype({'Variable_value':'uint64'})
    trx_log_data1['log_lsn_checkpoint_age'] = trx_log_data1['Variable_value']
    trx_log_data2 = data[data['Variable_name'] == 'log_max_modified_age_async']
    trx_log_data2 = trx_log_data2.astype({'Variable_value':'uint64'})
    trx_log_data2['log_max_modified_age_async'] = trx_log_data2['Variable_value']

    trx_log_data = trx_log_data1[['timestamp', 'log_lsn_checkpoint_age']].merge(trx_log_data2[['timestamp','log_max_modified_age_async']])

    trx_log_data2 = data[data['Variable_name'] == 'log_max_modified_age_sync']
    trx_log_data2 = trx_log_data2.astype({'Variable_value':'uint64'})
    trx_log_data2['log_max_modified_age_sync'] = trx_log_data2['Variable_value']

    trx_log_data = trx_log_data.merge(trx_log_data2[['timestamp','log_max_modified_age_sync']])

    utilization = round((trx_log_data['log_lsn_checkpoint_age'] / 
                                                  trx_log_data['log_max_modified_age_async']) * 100,2)
    trx_log_data['async utilization %'] = utilization

    utilization = trx_log_data.apply(lambda x: _get_sync_pct(x,'log_lsn_checkpoint_age','log_max_modified_age_async', 'log_max_modified_age_sync'), axis=1)
    trx_log_data['sync utilization %'] = utilization
    mylegend = []
    min=trx_log_data['async utilization %'].min()
    max_val=trx_log_data['async utilization %'].max()
    mean=trx_log_data['async utilization %'].mean()
    mylegend.append("{} min={} max={} avg={}".format("async utilization %".ljust(35, " "), 
                                                          str(round(min)).ljust(20, " "), 
                                                          str(round(max_val)).ljust(20, " "), round(mean)))
    min=trx_log_data['sync utilization %'].min()
    max_val=trx_log_data['sync utilization %'].max()
    mean=trx_log_data['sync utilization %'].mean()
    mylegend.append("{} min={} max={} avg={}".format("sync utilization %".ljust(35, " "), 
                                                          str(round(min)).ljust(20, " "), 
                                                          str(round(max_val)).ljust(20, " "), round(mean)))
    ax=trx_log_data[["timestamp","async utilization %", "sync utilization %"]].plot(kind="area",stacked=False, 
                    title="MySQL InnoDB Transaction Log Utilization", figsize=(10.24,7.68), legend=False)
    h,l = ax.get_legend_handles_labels()
    font = font_manager.FontProperties(family='FantasqueSansMono-Regular.ttf+Powerline+Awesome',
                                   style='normal', size=11)
    ax.legend(h, mylegend, loc='upper center',bbox_to_anchor=(0.5, -0.05), shadow=True, ncol=1, prop=font)
    file_name = "{}/{}".format(common.outdir, "innodb_trx_log_util.png")
    ax.figure.savefig(file_name)
    print("Plot {} generated.".format(file_name))
    plt.close('all')

    return
