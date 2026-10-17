# AMD GPU and Quark feasibility — Phase 4

## Measured environment

Read-only diagnostics are saved in `reports/phase4/hardware.json`. This checkout
runs on Windows 11 / Python 3.12.7. Windows reports `AMD Radeon(TM) Graphics` and
`NVIDIA GeForce RTX 3060 Laptop GPU`. `rocminfo`, `rocm-smi` and `amd-smi` are not
installed; there is no ROCm version file or PyTorch installation. No working AMD
HIP device, usable GPU memory or model execution has been established. Windows
AdapterRAM is a limited driver field, not a verified dedicated VRAM measurement.
Token Factory credentials provide hosted inference, not control of its GPUs.

No ROCm backend, GPU package installation, GPU rental, GPU benchmark or Quark
processing was performed. CPU faster-whisper remains the application backend.

## Notebook intake

On a separately provided notebook, run this read-only command in its existing
environment before installing anything:

```bash
python scripts/gpu_diagnostics.py --output notebook-hardware.json
```

It collects GPU identifiers (`lspci` on Linux, Windows display devices otherwise),
`rocminfo`, ROCm version, `rocm-smi` utilization/VRAM, `amd-smi` version, system
memory and, when PyTorch already exists, its version, `torch.version.hip`,
`torch.cuda.is_available()`, device identities and free/total device memory.
PyTorch's `torch.cuda` namespace also represents HIP devices; CUDA availability
alone on this RTX laptop would not prove AMD support. No package/model download
or model execution occurs. Confirm physical GPU access on the actual notebook.

Check its exact GPU architecture, OS, driver and PyTorch version against
[AMD's versioned compatibility matrices](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html)
and the current release documentation linked there. AMD documents native Windows
support for specific devices; this report does not assume every Radeon is supported.
The generic integrated adapter name here is insufficient to establish compatibility.

[CTranslate2's prebuilt hardware support](https://opennmt.net/CTranslate2/hardware_support.html)
lists CPU and NVIDIA GPU paths; the installed faster-whisper/CTranslate2 path is
not an established ROCm runtime. A candidate for a supported HIP notebook is a
separate [PyTorch Whisper implementation](https://github.com/openai/whisper), after
matching its dependencies to that notebook. This is a feasibility proposal, not
an installed or validated backend.

If HIP is verified, first execute one local-weight Whisper model outside DubGuard.
Only after that succeeds should an optional adapter implement `ASRProvider` and
return source-relative `ASRHypothesis` spans through the existing coverage pipeline.
Never silently substitute it for CPU or remove uncertainty. Do not implement a
backend based only on a device inventory.

For a meaningful comparison, keep identical original audio SHA-256, normalized
PCM, model family/size/revision and decoding parameters. Record warm/cold load and
wall processing time separately, synchronize the HIP device before timing, sample
GPU utilization/peak memory, and retain transcripts/timestamps. Compare a PyTorch
CPU run against the same PyTorch weights on HIP to isolate device effects; label
faster-whisper int8 versus PyTorch fp16 as a combined runtime/precision comparison.
Measure protected number/polarity errors only against independently listened-to
human ground truth. No speedup, error rate or transcript equivalence is asserted here.

## Quark decision

The current [AMD Quark PyTorch PTQ documentation](https://quark.docs.amd.com/latest/pytorch/example_quark_torch_llm_ptq.html)
lists supported language-model families and INT/FP8/MX recipes. Whisper is not
listed in that example's supported-model table. This is not proof that all custom
Whisper quantization is impossible. It does mean this checkout has no documented,
validated Quark-to-Whisper-to-CTranslate2 path ready for its demonstration.

The local application uses converted CTranslate2 Whisper weights and CPU int8
inference; that is **not AMD Quark processing**. It owns no locally loaded PyTorch
LLM. DeepSeek-V4-Flash and MiMo-V2.6-Flash are hosted services, whose weights and
runtime the project does not control. Even a Quark-supported DeepSeek family
does not make the hosted endpoint quantizable by this application.

Decision: stop this experimental branch for the current demo. Do not add Quark
dependencies or claim Quark/GPU/ROCm use in the submission. Revisit only with
supported locally controlled weights, an isolated compatible runtime and verified
speech data. A future experiment must retain original/quantized model bytes,
memory, latency, output correctness, and protected-number/polarity preservation;
an inaccurate quantized model cannot replace the working pipeline. No such metrics
are available now.
