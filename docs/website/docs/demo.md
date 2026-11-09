# Demo

A short terminal tour of CodeGreen 0.5.0. Every output below is from a real
run on an AMD EPYC 9554P host with an NVIDIA RTX 5000 Ada GPU; long outputs
are trimmed to their result lines.

## 1. Check the installation

```console
$ codegreen --version
CodeGreen version 0.5.0
$ codegreen doctor
...
Sensor selection: all (every provider that initializes)
  - amd_gpu: did not initialize: initialize or self_test failed; the provider logged no reason
  - amd_rapl: did not initialize: amd_rapl: /dev/cpu/0/msr: Permission denied (needs the msr module,
read access to the device and CAP_SYS_RAWIO)
  - arm_eas: did not initialize: initialize or self_test failed; the provider logged no reason
   intel_rapl: initialized
   nvidia_gpu: initialized
 NVIDIA GPU: NVIDIA RTX 5000 Ada Generation
 RAPL access: Can access 1 RAPL energy files

Diagnosis Summary:
 No issues found! CodeGreen appears to be properly installed.
```

`intel_rapl` is the Linux powercap RAPL interface, used on AMD CPUs too. On
Linux, `sudo codegreen init-sensors` grants RAPL read access once.

## 2. Measure any command

```console
$ codegreen run --repeat 5 --sensors rapl -- python3 lookup_list.py
...
Energy: 85.3807 J +/- 1.3071 J
  CV:    1.5% (excellent)
Time:   1.0806 s +/- 0.0022 s
Validity: valid
```

## 3. Find the expensive function

```console
$ codegreen analyze python sorting_comparison.py
...
Instrumentation points: 8
...
$ codegreen measure python sorting_comparison.py -g fine --sensors rapl
...
Energy: 82.6265 J
Time:   1.0699 s
Power:  77.23 W

  Function                         Excl J     Incl J    Calls  Quality
  bubble_sort                     81.1461    81.1461        1  measured
  quick_sort                       1.3354    16.1971     5581  aggregate_only
  generate_data                    0.1394     0.1394        1  below_resolution
  main                             0.0056    82.6265        1  measured
Validity: valid
```

## 4. Profile a project

```console
$ codegreen project python . --run-cmd "python3 main.py" --sensors rapl
...
  Rank  Function                              Excl%   Incl%   Self  Verdict    Calls    uJ/call
  ----------------------------------------------------------------------------------------------------
  1     heavy                                 96.3%   96.3%  1.00 TYPE_2_INEFFICIENT        1 19834337.0
  2     medium                                 3.7%    3.7%  1.00    minor        1   757954.0
  3     light                                  0.0%    0.0%  1.00    minor        1     1762.0
Validity: valid
```

## Where next

- The scripts: [Python deep dive](examples/python.md) (steps 2 and 3),
  [09 - Project hotspots (Python)](examples/09_project_hotspots_python.md)
  (step 4).
- [Quick Start](getting-started/quickstart.md) and the
  [CLI reference](user-guide/cli-reference.md).
