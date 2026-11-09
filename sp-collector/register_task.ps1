# 注册采集器计划任务（当前用户交互模式，无窗口 pythonw）
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File register_task.ps1
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat = Join-Path $dir 'run_collector.bat'

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>球多多竞彩采集器（watchdog 自重启）</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT15S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$(whoami)</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>P365D</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c "$bat"</Arguments>
      <WorkingDirectory>$dir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

try {
  $svc = New-Object -ComObject 'Schedule.Service'
  $svc.Connect()
  $folder = $svc.GetFolder('\')
  $def = $svc.NewTask(0)
  $def.XmlText = $xml
  # 6 = TASK_CREATE_OR_UPDATE, 3 = TASK_LOGON_INTERACTIVE_TOKEN
  $folder.RegisterTaskDefinition('JieqiuSPCollector', $def, 6, $null, $null, 3) | Out-Null
  Set-Content -Path (Join-Path $dir 'register_result.txt') -Value "ok $(Get-Date -Format s)"
  Write-Output 'registered: JieqiuSPCollector'
} catch {
  Set-Content -Path (Join-Path $dir 'register_result.txt') -Value "fail: $($_.Exception.Message)"
  throw
}
