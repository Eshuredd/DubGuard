"""Read-only notebook/runtime inventory. No installs, model downloads, or inference."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


def command(args):
    if not shutil.which(args[0]):
        return {"status": "not_installed"}
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return {"status": "ok" if result.returncode == 0 else "failed",
                "exit_code": result.returncode, "output": result.stdout[:20000],
                "stderr": result.stderr[:1000]}
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable_or_timeout"}


def collect():
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "cpu_count": os.cpu_count(), "inference_performed": False,
              "rocminfo": command(["rocminfo"]),
              "rocm_smi": command(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--showuse"]),
              "amd_smi": command(["amd-smi", "version"])}
    version = Path('/opt/rocm/.info/version')
    report['rocm_version_file'] = version.read_text().strip() if version.is_file() else None
    if platform.system() == 'Windows':
        report['hardware'] = command(['powershell', '-NoProfile', '-Command',
            'Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json'])
        report['system_memory'] = command(['powershell', '-NoProfile', '-Command',
            'Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json'])
    else:
        report['hardware'] = command(['lspci', '-nn'])
        report['system_memory'] = command(['free', '-b'])
    report['torch'] = {'installed': bool(importlib.util.find_spec('torch'))}
    if report['torch']['installed']:
        try:
            import torch
            report['torch'].update(version=torch.__version__, hip=torch.version.hip,
                                   cuda_available=torch.cuda.is_available())
            if torch.version.hip and torch.cuda.is_available():
                report['torch']['devices'] = [
                    {'name': torch.cuda.get_device_name(i),
                     'total_memory': torch.cuda.get_device_properties(i).total_memory,
                     'free_and_total_memory': list(torch.cuda.mem_get_info(i))}
                    for i in range(torch.cuda.device_count())]
        except Exception:
            report['torch']['status'] = 'import_or_runtime_failed'
    report['amd_gpu_runtime_confirmed'] = bool(report['torch'].get('hip') and report['torch'].get('cuda_available'))
    report['next_step'] = ('Check exact GPU/OS support and run an isolated Whisper benchmark before adding a backend.'
        if report['amd_gpu_runtime_confirmed'] else 'Stop GPU experiments until a supported AMD GPU notebook and working HIP runtime are supplied.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    encoded = json.dumps(collect(), indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
        print(args.output)
    else:
        print(encoded)
