Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
foreach ($v in $s.GetInstalledVoices()) {
    $i = $v.VoiceInfo
    Write-Output ($i.Name + ' | ' + $i.Gender + ' | ' + $i.Culture)
}
