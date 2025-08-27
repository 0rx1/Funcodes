function Get-ConnectionsFallback {
    [CmdletBinding()]
    param()

    $results = @()

    # 1) Preferred: try Get-NetTCPConnection (works on Win8+/Server2012+ if CIM is fine)
    try {
        $tcp = Get-NetTCPConnection -ErrorAction Stop
        foreach ($c in $tcp) {
            $procName = (Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue |
                         Select-Object -ExpandProperty ProcessName -ErrorAction SilentlyContinue)
            $results += [PSCustomObject]@{
                Protocol      = 'TCP'
                LocalAddress  = $c.LocalAddress
                LocalPort     = $c.LocalPort
                RemoteAddress = $c.RemoteAddress
                RemotePort    = $c.RemotePort
                State         = $c.State
                PID           = $c.OwningProcess
                Process       = $procName
            }
        }
        if ($results.Count -gt 0) { return $results }
    } catch {
        # fall back to netstat if Get-NetTCPConnection fails (CIM/WMI issues)
    }

    # 2) Robust netstat -ano parser (works on older Windows too)
    $lines = netstat -ano 2>$null
    if (-not $lines) { Write-Error "netstat produced no output."; return $results }

    function Split-Endpoint {
        param($endpoint)
        # handles [ipv6]:port or host:port
        if ($endpoint -match '^\[(.+)\]:(\d+)$') { return @{ Address=$matches[1]; Port=[int]$matches[2] } }
        elseif ($endpoint -match '^(.+):(\d+)$') { return @{ Address=$matches[1]; Port=[int]$matches[2] } }
        else { return @{ Address=$endpoint; Port=$null } }
    }

    foreach ($line in $lines) {
        $txt = $line.Trim()
        if ($txt -eq '' -or $txt -match '^(Proto|Active)') { continue }
        if ($txt -match '^(TCP|UDP)\s+') {
            # split on whitespace but remove empty tokens
            $parts = ($txt -split '\s+') | Where-Object { $_ -ne '' }

            # find last numeric token (PID) — more reliable than fixed index
            $pidToken = ($parts | Where-Object { $_ -match '^\d+$' } | Select-Object -Last 1)
            if (-not $pidToken) { continue }
            [int]$pid = [int]$pidToken

            $proto = $parts[0]
            if ($parts.Count -lt 3) { continue }
            $local  = $parts[1]
            $remote = $parts[2]

            $state = ''
            if ($proto -eq 'TCP' -and $parts.Count -ge 5) {
                # for TCP, the penultimate token is usually the State (e.g. LISTENING)
                $penultimate = $parts[-2]
                if ($penultimate -and ($penultimate -notmatch '^\d+$')) { $state = $penultimate }
            }

            $le = Split-Endpoint $local
            $re = Split-Endpoint $remote

            $procName = (Get-Process -Id $pid -ErrorAction SilentlyContinue |
                         Select-Object -ExpandProperty ProcessName -ErrorAction SilentlyContinue)

            $results += [PSCustomObject]@{
                Protocol      = $proto
                LocalAddress  = $le.Address
                LocalPort     = $le.Port
                RemoteAddress = $re.Address
                RemotePort    = $re.Port
                State         = $state
                PID           = $pid
                Process       = $procName
            }
        }
    }

    return $results
}

# Run and display:
$all = Get-ConnectionsFallback
$all | Sort-Object Protocol, LocalAddress, LocalPort | Format-Table -AutoSize
# $all | Export-Csv .\connections.csv -NoTypeInformation
