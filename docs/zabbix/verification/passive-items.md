# 패시브 체크 실측 결과 (2026-10-14T16:41:37+09:00)

> 한 줄 요약: Windows 패시브 체크 116개 key 실측 결과 표(요약 근거 자료).

- 대상: 127.0.0.1:10050, 키 116개, 성공 106개, 워밍업 65s 후 2차 측정값
- source: template=공식 Windows 템플릿 사용 키, extra=분석용 추가 확인, expect-unsupported=문서상 Windows 미지원 확인용

| 분류 | Item key | source | 결과 | 값(요약) / 오류 | 1차 측정 | ms |
|---|---|---|---|---|---|---|
| agent | `agent.ping` | template | 성공 | 1 | ok | 15 |
| agent | `agent.version` | template | 성공 | 7.0.31 | ok | 10 |
| agent | `agent.variant` | extra | 성공 | 2 | ok | 10 |
| agent | `agent.hostname` | template | 성공 | <호스트> | ok | 10 |
| system | `system.hostname` | template | 성공 | demo-host-01 | ok | 10 |
| system | `system.hostname[fqdn]` | extra | 성공 | demo-host-01 | ok | 10 |
| system | `system.uname` | template | 성공 | Windows demo-host-01 10.0.19045 Microsoft Windows 10 Pro x64 | ok | 43 |
| system | `system.sw.os` | template | 성공 | Windows 10 Pro 19041.1.amd64fre.vb_release.191206-1406 Build 19045.6466 | ok | 9 |
| system | `system.sw.os.get` | extra | 성공 | JSON 객체 (키: os_type, product_name, architecture, build_number, build_revision, build, edition, composition) | ok | 9 |
| system | `system.sw.arch` | template | 성공 | x64 | ok | 9 |
| system | `system.uptime` | template | 성공 | 265717 | ok | 12 |
| system | `system.localtime` | template | 성공 | 1791963765 | ok | 9 |
| system | `system.boottime` | expect-unsupported | 실패 | Unknown metric system.boottime | 실패: Unknown metric system.boottime | 9 |
| system | `system.users.num` | extra | 성공 | 1 | ok | 9 |
| system | `wmi.get[root\cimv2,"select LastBootUpTime from Win32_OperatingSystem"]` | extra | 성공 | 20261011145408.503145+540 | ok | 30 |
| system | `registry.data["HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion",DisplayVersion]` | extra | 성공 | 22H2 | ok | 9 |
| cpu | `system.cpu.util` | template | 성공 | 10.951853 | ok | 9 |
| cpu | `system.cpu.util[,system]` | extra | 성공 | 10.951853 | ok | 9 |
| cpu | `system.cpu.util[0]` | extra | 성공 | 24.272750 | ok | 9 |
| cpu | `system.cpu.util[,user]` | expect-unsupported | 실패 | Invalid second parameter. | 실패: Invalid second parameter. | 10 |
| cpu | `system.cpu.util[,,avg5]` | expect-unsupported | 성공 | 11.498184 | ok | 9 |
| cpu | `system.cpu.load` | extra | 성공 | 0.000000 | ok | 9 |
| cpu | `system.cpu.load[percpu,avg1]` | extra | 성공 | 0.000000 | ok | 9 |
| cpu | `system.cpu.load[all,avg5]` | extra | 성공 | 0.000000 | ok | 9 |
| cpu | `system.cpu.num` | extra | 성공 | 12 | ok | 9 |
| cpu | `system.cpu.discovery` | extra | 성공 | JSON 배열 12개 (첫 항목 키: {#CPU.NUMBER}, {#CPU.STATUS}) | ok | 9 |
| cpu | `wmi.get[root/cimv2,"Select NumberOfLogicalProcessors from Win32_ComputerSystem"]` | template | 성공 | 12 | ok | 33 |
| cpu | `perf_counter_en["\Processor Information(_total)\% Processor Time"]` | extra | 성공 | 2.986834 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| cpu | `perf_counter_en["\Processor Information(_total)\% Processor Utility"]` | extra | 성공 | 5.836891 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| cpu | `perf_counter_en["\Processor Information(_total)\% User Time"]` | template | 성공 | 1.434343 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| cpu | `perf_counter_en["\Processor Information(_total)\% Privileged Time"]` | template | 성공 | 2.738270 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| cpu | `perf_counter_en["\Processor Information(_total)\% Interrupt Time"]` | template | 성공 | 0.521573 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| cpu | `perf_counter_en["\Processor Information(_total)\% DPC Time"]` | template | 성공 | 0.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| cpu | `perf_counter_en["\System\Processor Queue Length"]` | template | 성공 | 0.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| cpu | `perf_counter_en["\System\Context Switches/sec"]` | template | 성공 | 12276.015311 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| cpu | `perf_counter["\Processor(_Total)\% Processor Time"]` | extra | 성공 | 2.978604 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| memory | `vm.memory.size[total]` | template | 성공 | 17111175168 | ok | 9 |
| memory | `vm.memory.size[used]` | template | 성공 | 9190973440 | ok | 9 |
| memory | `vm.memory.size[available]` | extra | 성공 | 7919960064 | ok | 9 |
| memory | `vm.memory.size[free]` | extra | 성공 | 7919603712 | ok | 9 |
| memory | `vm.memory.size[pused]` | extra | 성공 | 53.721084 | ok | 9 |
| memory | `vm.memory.size[pavailable]` | extra | 성공 | 46.276475 | ok | 9 |
| memory | `vm.memory.util` | expect-unsupported | 실패 | Unknown metric vm.memory.util | 실패: Unknown metric vm.memory.util | 9 |
| memory | `vm.vmemory.size[total]` | extra | 성공 | 20198182912 | ok | 9 |
| memory | `vm.vmemory.size[used]` | extra | 성공 | 12718604288 | ok | 9 |
| memory | `vm.vmemory.size[available]` | extra | 성공 | 7480905728 | ok | 9 |
| memory | `vm.vmemory.size[pused]` | extra | 성공 | 62.967065 | ok | 9 |
| memory | `system.swap.size[,total]` | template | 성공 | 3087007744 | ok | 9 |
| memory | `system.swap.size[,free]` | extra | 성공 | 0 | ok | 9 |
| memory | `system.swap.size[,pfree]` | extra | 성공 | 0.000000 | ok | 9 |
| memory | `system.swap.size[,pused]` | extra | 성공 | 100.000000 | ok | 9 |
| memory | `perf_counter_en["\Paging file(_Total)\% Usage"]` | template | 성공 | 5.887504 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| memory | `perf_counter_en["\Memory\Cache Bytes"]` | template | 성공 | 527872000.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| memory | `perf_counter_en["\Memory\Free System Page Table Entries"]` | template | 성공 | 12507286.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| memory | `perf_counter_en["\Memory\Page Faults/sec"]` | template | 성공 | 34261.652523 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| memory | `perf_counter_en["\Memory\Pages/sec"]` | template | 성공 | 0.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| memory | `perf_counter_en["\Memory\Pool Nonpaged Bytes"]` | template | 성공 | 503599104.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| memory | `perf_counter_en["\Memory\Available MBytes"]` | extra | 성공 | 7549.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| memory | `perf_counter_en["\Memory\% Committed Bytes In Use"]` | extra | 성공 | 62.965645 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `vfs.fs.discovery` | extra | 성공 | JSON 배열 1개 (첫 항목 키: {#FSNAME}, {#FSTYPE}, {#FSLABEL}, {#FSDRIVETYPE}) | ok | 13 |
| disk | `vfs.fs.get` | template | 성공 | JSON 배열 1개 (첫 항목 키: fsname, fstype, fslabel, fsdrivetype, bytes, options) | ok | 14 |
| disk | `vfs.fs.size[C:,total]` | extra | 성공 | 119325487104 | ok | 9 |
| disk | `vfs.fs.size[C:,used]` | extra | 성공 | 109611593728 | ok | 9 |
| disk | `vfs.fs.size[C:,free]` | extra | 성공 | 9713893376 | ok | 9 |
| disk | `vfs.fs.size[C:,pused]` | extra | 성공 | 91.859331 | ok | 9 |
| disk | `vfs.fs.size[C:,pfree]` | extra | 성공 | 8.140669 | ok | 9 |
| disk | `vfs.fs.inode[C:,pfree]` | expect-unsupported | 실패 | Unknown metric vfs.fs.inode | 실패: Unknown metric vfs.fs.inode | 9 |
| disk | `perf_instance_en.discovery[PhysicalDisk]` | template | 성공 | JSON 배열 2개 (첫 항목 키: {#INSTANCE}) | ok | 31 |
| disk | `vfs.dev.discovery` | expect-unsupported | 실패 | Unknown metric vfs.dev.discovery | 실패: Unknown metric vfs.dev.discovery | 10 |
| disk | `vfs.dev.read[,ops]` | expect-unsupported | 실패 | Unknown metric vfs.dev.read | 실패: Unknown metric vfs.dev.read | 9 |
| disk | `wmi.getall[root\cimv2,"select Index,Model,Status,Size from Win32_DiskDrive"]` | extra | 성공 | JSON 배열 1개 (첫 항목 키: DeviceID, Index, Model, Size, Status) | ok | 37 |
| network | `net.if.discovery` | template | 성공 | JSON 배열 9개 (첫 항목 키: {#IFNAME}, {#IFGUID}) | ok | 9 |
| network | `net.if.list` | extra | 성공 | 9줄 텍스트 (첫 줄: Ethernet                  enabled  - Realtek PCIe GbE Family) | ok | 11 |
| network | `wmi.getall[root\cimv2,"select Name,Description,NetConnectionID,Speed,AdapterTypeId,NetConnectionStatus,GUID from win32_networkadapter where PhysicalAdapter=True and NetConnectionStatus>0"]` | template | 성공 | JSON 배열 1개 (첫 항목 키: AdapterTypeId, Description, DeviceID, GUID, Name, NetConnectionID) | ok | 42 |
| network | `net.tcp.port[127.0.0.1,10050]` | extra | 성공 | 1 | ok | 9 |
| network | `net.tcp.listen[10050]` | extra | 성공 | 1 | ok | 10 |
| network | `net.tcp.socket.count[,10050]` | extra | 성공 | 194 | ok | 12 |
| network | `net.dns[,www.zabbix.com,A,2,1]` | extra | 성공 | 1 | ok | 13 |
| service | `service.discovery` | template | 성공 | JSON 배열 271개 (첫 항목 키: {#SERVICE.NAME}, {#SERVICE.DISPLAYNAME}, {#SERVICE.DESCRIPTION}, {#SERVICE.STATE}, {#SERVICE.STATENAME}, {#SERVICE.PATH}) | ok | 104 |
| service | `service.info[EventLog]` | extra | 성공 | 0 | ok | 9 |
| service | `service.info[EventLog,startup]` | extra | 성공 | 0 | ok | 9 |
| service | `service.info[Dnscache,state]` | extra | 성공 | 0 | ok | 9 |
| service | `service.info[Winmgmt,displayname]` | extra | 성공 | Windows Management Instrumentation | ok | 10 |
| service | `service.info[NoSuchService_Test]` | extra | 성공 | 255 | ok | 9 |
| service | `services[automatic,stopped]` | extra | 성공 | 6줄 텍스트 (첫 줄: edgeupdate) | ok | 81 |
| process | `proc.num[]` | template | 성공 | 211 | ok | 13 |
| process | `proc.num[svchost.exe]` | extra | 성공 | 70 | ok | 13 |
| process | `perf_counter_en["\System\Threads"]` | template | 성공 | 2882.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| process | `perf_counter_en["\System\Processes"]` | extra | 성공 | 211.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| process | `proc_info[svchost.exe,wkset,sum]` | extra | 성공 | 137748.000000 | ok | 14 |
| process | `proc_info[svchost.exe,io_read_b,sum]` | extra | 성공 | 17479029.000000 | ok | 14 |
| process | `proc_info[svchost.exe,utime,sum]` | extra | 성공 | 10465.000000 | ok | 13 |
| process | `proc.get[,,,summary]` | extra | 성공 | JSON 배열 38개 (첫 항목 키: name, processes, vmsize, wkset, cputime_user, cputime_system) | ok | 27 |
| process | `perf_counter_en["\Process(svchost)\% Processor Time",60]` | extra | 성공 | 0.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| process | `wmi.getall[root\cimv2,"select Name,IDProcess,PercentProcessorTime,WorkingSetPrivate from Win32_PerfFormattedData_PerfProc_Process where Name<>'_Total' and Name<>'Idle' and PercentProcessorTime>0"]` | extra | 성공 | JSON 배열 2개 (첫 항목 키: IDProcess, Name, PercentProcessorTime, WorkingSetPrivate) | ok | 351 |
| process | `proc.cpu.util[]` | expect-unsupported | 실패 | Unknown metric proc.cpu.util | 실패: Unknown metric proc.cpu.util | 9 |
| process | `proc.mem[]` | expect-unsupported | 실패 | Unknown metric proc.mem | 실패: Unknown metric proc.mem | 9 |
| eventlog | `eventlog[System]` | expect-unsupported | 실패 | The "eventlog" key is not supported in test or single passive check mode | 실패: The "eventlog" key is not supported in test or single pa | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Disk Reads/sec",60]` | template | 성공 | 0.366451 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Disk Writes/sec",60]` | template | 성공 | 14.245746 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Current Disk Queue Length",60]` | template | 성공 | 0.000000 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\% Idle Time",60]` | template | 성공 | 99.417771 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Avg. Disk sec/Read",60]` | template | 성공 | 0.000122 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Avg. Disk sec/Write",60]` | template | 성공 | 0.000201 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Avg. Disk Read Queue Length",60]` | template | 성공 | 0.000434 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Avg. Disk Write Queue Length",60]` | template | 성공 | 0.002986 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Disk Read Bytes/sec",60]` | extra | 성공 | 9562.105572 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| disk | `perf_counter_en["\PhysicalDisk(0 C:)\Disk Write Bytes/sec",60]` | extra | 성공 | 195959.193866 | 실패: Received empty response from Zabbix Agent at [127.0.0.1] | 9 |
| network | `net.if.in["{A7EDAA52-E3D4-4B2C-BE74-55BADBF9FE84}"]` | template | 성공 | 8093716384 | ok | 9 |
| network | `net.if.out["{A7EDAA52-E3D4-4B2C-BE74-55BADBF9FE84}"]` | template | 성공 | 887879162 | ok | 9 |
| network | `net.if.in["{A7EDAA52-E3D4-4B2C-BE74-55BADBF9FE84}",errors]` | template | 성공 | 0 | ok | 9 |
| network | `net.if.out["{A7EDAA52-E3D4-4B2C-BE74-55BADBF9FE84}",errors]` | template | 성공 | 0 | ok | 9 |
| network | `net.if.in["{A7EDAA52-E3D4-4B2C-BE74-55BADBF9FE84}",dropped]` | template | 성공 | 1128 | ok | 9 |
| network | `net.if.out["{A7EDAA52-E3D4-4B2C-BE74-55BADBF9FE84}",dropped]` | template | 성공 | 0 | ok | 9 |
| network | `net.if.total["{A7EDAA52-E3D4-4B2C-BE74-55BADBF9FE84}"]` | extra | 성공 | 8981595546 | ok | 10 |
| network | `net.if.in["이더넷"]` | extra | 실패 | Cannot obtain network interface information. | 실패: Cannot obtain network interface information. | 9 |
