#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import socket
import statistics
import struct
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "amiga.json"
START_TIMEOUT = 120
FINAL_TIMEOUT = 70
REPLAY_TIMEOUT = 600
FRAME_SIZE = 7690
GAME_HASHES = {
    "AUDIO.CK4": "66dcf6070a4bc5c8933815b15dab7145ddcccb959f8f43af2a0449b085a04366",
    "EGAGRAPH.CK4": "9805168fb910385ad40455541cbcfa1aaa61f9d81b2504274ee0ca0ec4b71550",
    "GAMEMAPS.CK4": "01186f8cb99257b69a4f475186deb9ba79b872ed52378131c79c21f6344753ea",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_game_data(directory):
    failures = []
    for name, expected in GAME_HASHES.items():
        path = directory / name
        if not path.is_file():
            failures.append(f"missing {name}")
        elif sha256(path) != expected:
            failures.append(f"hash mismatch {name}")
    return failures


def read_record(path):
    if not path.is_file():
        return None
    content = path.read_text(errors="replace")
    if not content.endswith("\n"):
        return None
    data = {}
    for line in content.splitlines():
        if "=" not in line:
            raise ValueError(f"malformed record: {path.name}")
        key, value = line.split("=", 1)
        if not key or key in data:
            raise ValueError(f"duplicate or empty field: {path.name}")
        data[key] = value
    return data


def check_identity(record, run_id, build_id, label):
    if record is None:
        return f"missing {label}"
    if record.get("run_id") != run_id or record.get("build_id") != build_id:
        return f"{label} has wrong run or build ID"
    return None


def verify_completion(result_dir, run_id, build_id):
    start = read_record(result_dir / f"{run_id}.start")
    final = read_record(result_dir / f"{run_id}.result")
    returned = read_record(result_dir / "returned")
    for label, record in (("start", start), ("result", final), ("returned", returned)):
        error = check_identity(record, run_id, build_id, label)
        if error:
            return error
    if start.get("state") != "started":
        return "start has wrong state"
    if final.get("state") != "finished":
        return "result has wrong state"
    if final.get("result") != "pass":
        return "guest result is not pass"
    return None


def load_config(path):
    data = json.loads(path.read_text())
    keys = ("amiberry", "rom", "system_base", "game_data", "runs_dir")
    for key in keys:
        if key not in data or not isinstance(data[key], str):
            raise ValueError(f"config needs {key}")
        value = Path(data[key]).expanduser()
        if not value.is_absolute():
            raise ValueError(f"{key} must be absolute")
        data[key] = value.resolve()
    for key in ("amiberry", "rom", "system_base", "game_data"):
        if not data[key].exists():
            raise ValueError(f"{key} does not exist: {data[key]}")
    local_root = (ROOT / "local").resolve()
    if not data["runs_dir"].is_relative_to(local_root):
        raise ValueError("runs_dir must be inside the repository's local directory")
    if data["runs_dir"].is_relative_to(data["system_base"]) or \
       data["system_base"].is_relative_to(data["runs_dir"]):
        raise ValueError("runs_dir and system_base must be separate")
    startup = data["system_base"] / "S" / "Startup-Sequence"
    if not startup.is_file() or "execute test:run-test" not in startup.read_text().lower():
        raise ValueError("system_base must execute TEST:run-test from Startup-Sequence")
    return data


def stage_run(config, run_id, build_id, executable, interactive,
              mode="probe", demo=None, audible=False, audio=False, cycles=1):
    run_dir = config["runs_dir"] / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    for name in ("test", "results", "home"):
        (run_dir / name).mkdir()
    shutil.copytree(config["system_base"], run_dir / "system")
    if mode == "probe":
        shutil.copy2(executable, run_dir / "test" / "keen-probe")
        guest_command = (
            f"TEST:keen-probe --run-id {run_id} --build-id {build_id} "
            f"--result-dir RESULT:{' --interactive' if interactive else ''}"
            f"{' --audible' if audible else ''}"
        )
    else:
        shutil.copy2(executable, run_dir / "test" / "omnispeak")
        for path in (ROOT / "data" / "keen4").iterdir():
            if path.is_file():
                shutil.copy2(path, run_dir / "test" / path.name)
        for name in GAME_HASHES:
            shutil.copy2(config["game_data"] / name, run_dir / "test" / name)
        guest_command = (
            f"TEST:omnispeak /RUNID {run_id} /BUILDID {build_id} "
            f"/EPISODE 4 /NOBORDER /NOCOPY"
        )
        if mode in ("replay", "stress"):
            guest_command += " /AUTOTEST"
            if not audio:
                guest_command += " /NOSOUND"
            guest_command += f" /PLAYDEMO {demo} /DUMPFILE RESULT:actual.dump"
            if mode == "stress":
                guest_command += f" /STRESS {cycles}"
    lines = [
        "Stack 262144",
        "CD TEST:",
        guest_command + " >RESULT:console.txt",
        f'Echo "run_id={run_id}" >RESULT:returned.tmp',
        f'Echo "build_id={build_id}" >>RESULT:returned.tmp',
        "Rename RESULT:returned.tmp RESULT:returned",
    ]
    (run_dir / "test" / "run-test").write_text("\n".join(lines) + "\n")
    return run_dir, guest_command


def command_for(config, run_dir, jit, audible=False):
    cpu = config.get("cpu", "68040")
    fpu = "0" if cpu == "68020" else "68040"
    options = [
        f"filesystem2=rw,DH0:System:{run_dir / 'system'},0",
        f"filesystem2=rw,DH1:TEST:{run_dir / 'test'},-1",
        f"filesystem2=rw,DH2:RESULT:{run_dir / 'results'},-1",
        f"cpu_type={cpu}", f"cpu_model={cpu}", f"fpu_model={fpu}",
        "cpu_speed=max", "cpu_compatible=false", "cpu_24bit_addressing=false",
        "cpu_cycle_exact=false", "cpu_memory_cycle_exact=false",
        "blitter_cycle_exact=false",
        f"cachesize={8192 if jit else 0}", "z3mem_size=64",
        "gfxcard_type=ZorroIII", "gfxcard_size=8",
        "gfx_width_windowed=640", "gfx_height_windowed=480",
        "gfx_fullscreen_amiga=false", "gfx_fullscreen_picasso=false",
        "sound_output=normal", f"sound_volume={0 if audible else 100}",
    ]
    args = [str(config["amiberry"]), "-o",
            f"amiberry_config={run_dir / 'home' / 'amiberry.conf'}",
            "-o", "write_logfile=yes", "--log", "--model", "A1200",
            "-r", str(config["rom"])]
    for option in options:
        args.extend(("-s", option))
    return args + ["-G"]


def check_profile(log_text, jit, cpu="68040"):
    cpu_lines = re.findall(r"^CPU=\d+[^\n]*", log_text, re.MULTILINE)[:1]
    if not cpu_lines or not cpu_lines[0].startswith(f"CPU={cpu},"):
        return "missing effective CPU/JIT profile in emulator log"
    if cpu == "68020" and not re.search(r"FPU=0(?:,|\s)", cpu_lines[-1]):
        return "68020 profile must have no FPU"
    if jit:
        caches = re.findall(r"actual translation cache size : (\d+) KB", log_text)
        active = re.search(r"JIT=CPU/FPU=(\d+)", cpu_lines[-1])
        if not caches or not active or caches[-1] != "8192" or active.group(1) != "8192":
            return f"effective JIT profile is wrong: {cpu_lines[-1]}"
    else:
        caches = re.findall(r"JIT: cache=(\d+)\.", log_text)
        active = re.search(r"JIT=(\d+)", cpu_lines[-1])
        if not caches or not active or caches[-1] != "0" or active.group(1) != "0":
            return f"effective non-JIT profile is wrong: {cpu_lines[-1]}"
    return None


def stop_owned_process(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def owns_ipc_socket(pid, path):
    try:
        result = subprocess.run(
            ["lsof", "-nP", "-a", "-p", str(pid), "-U", "-Fn"],
            capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and f"n{path}" in result.stdout.splitlines()


def send_ipc(command, path):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(path)
        connection.sendall((command + "\n").encode())
        return connection.recv(4096).decode(errors="replace").strip()


def collect_ipc(process, run_dir, label=""):
    ipc_path = "/tmp/amiberry.sock"
    if not owns_ipc_socket(process.pid, ipc_path):
        return "skipped: IPC socket ownership unverified"
    try:
        status = send_ipc("GET_STATUS", ipc_path)
        (run_dir / f"ipc-status{label}.txt").write_text(status + "\n")
        image_path = run_dir / f"screen{label}.png"
        reply = send_ipc(f"SCREENSHOT\t{image_path}", ipc_path)
        (run_dir / f"ipc-screenshot{label}.txt").write_text(reply + "\n")
        return "captured" if image_path.is_file() else f"failed: {reply}"
    except OSError as exc:
        return f"failed: {exc}"


def wait_for_completion(process, result_dir, run_id, build_id, interactive,
                        capture=None, mode="probe", cycles=1,
                        run_timeout_seconds=0):
    start_deadline = time.monotonic() + START_TIMEOUT
    started_at = time.monotonic()
    final_deadline = (started_at + REPLAY_TIMEOUT if mode == "replay" else
                      started_at + run_timeout_seconds
                      if mode == "run" and run_timeout_seconds else None)
    cycle_deadline = None
    completed_cycles = 0
    first_start = None
    captured = False
    while True:
        now = time.monotonic()
        start_path = result_dir / f"{run_id}.start"
        final_path = result_dir / f"{run_id}.result"
        returned_path = result_dir / "returned"
        try:
            start = read_record(start_path)
            returned = read_record(returned_path)
            final = read_record(final_path) if returned is not None else None
        except (OSError, ValueError) as exc:
            return f"invalid guest record: {exc}", first_start, now - started_at
        if start is not None and {"run_id", "build_id", "state"} <= start.keys():
            error = check_identity(start, run_id, build_id, "start")
            if error:
                return error, first_start, now - started_at
        else:
            start = None
        if returned is not None:
            error = check_identity(returned, run_id, build_id, "returned")
            if error:
                return error, first_start, now - started_at
        if start is not None and first_start is None:
            if start.get("state") != "started":
                return "start has wrong state", first_start, now - started_at
            first_start = now - started_at
            if mode == "stress":
                cycle_deadline = now + REPLAY_TIMEOUT
            elif mode not in ("replay", "run"):
                final_deadline = now + (FINAL_TIMEOUT if interactive else 45)
        if mode == "stress" and first_start is not None:
            while completed_cycles < cycles:
                number = completed_cycles + 1
                label = f"cycle{number:03d}"
                try:
                    cycle_record = read_record(result_dir / f"{run_id}.{label}")
                except (OSError, ValueError) as exc:
                    return f"invalid {label} record: {exc}", first_start, now - started_at
                if cycle_record is None:
                    break
                error = check_identity(cycle_record, run_id, build_id, label)
                if error:
                    return error, first_start, now - started_at
                if cycle_record.get("state") != "finished" or cycle_record.get("result") != "pass":
                    return f"invalid {label} completion", first_start, now - started_at
                completed_cycles = number
                cycle_deadline = now + REPLAY_TIMEOUT
        if capture is not None and first_start is not None and not captured and \
           now - started_at >= first_start + 2:
            capture()
            captured = True
        if final is not None and returned is not None:
            error = verify_completion(result_dir, run_id, build_id)
            return error, first_start, now - started_at
        if process.poll() is not None:
            return "emulator exited before completion", first_start, now - started_at
        if first_start is None and now >= start_deadline:
            return "start timeout", first_start, now - started_at
        if final_deadline is not None and now >= final_deadline:
            return "final timeout", first_start, now - started_at
        if cycle_deadline is not None and now >= cycle_deadline:
            return "stress cycle timeout", first_start, now - started_at
        time.sleep(0.25)


def compare_dumps(actual_path, reference_path):
    actual = actual_path.read_bytes()
    reference = reference_path.read_bytes()
    detail = {
        "actual_bytes": len(actual), "reference_bytes": len(reference),
        "actual_sha256": hashlib.sha256(actual).hexdigest(),
        "reference_sha256": hashlib.sha256(reference).hexdigest(),
    }
    if len(reference) % FRAME_SIZE:
        return "reference has incomplete frame", detail
    if len(actual) % FRAME_SIZE:
        return "dump has incomplete frame", detail
    limit = min(len(actual), len(reference))
    for offset in range(limit):
        if actual[offset] != reference[offset]:
            frame, within = divmod(offset, FRAME_SIZE)
            detail["expected_tick"] = struct.unpack_from("<I", reference, frame * FRAME_SIZE)[0]
            detail["actual_tick"] = struct.unpack_from("<I", actual, frame * FRAME_SIZE)[0]
            if within < 4:
                field = f"tick offset {within}"
            elif within < 90:
                field = f"game state offset {within - 4}"
            else:
                slot, member = divmod(within - 90, 76)
                field = f"object {slot} offset {member}"
            detail.update(frame=frame, offset=offset, field=field,
                          expected=reference[offset], actual=actual[offset])
            message = (f"first mismatch at frame {frame}, {field} "
                       f"(expected tick {detail['expected_tick']}, "
                       f"actual tick {detail['actual_tick']})")
            return message, detail
    if len(actual) != len(reference):
        return "dump length differs from reference", detail
    detail["frames"] = len(actual) // FRAME_SIZE
    return None, detail


def check_audio_metrics(metrics):
    if metrics is None or metrics.get("audio_opened") != "1":
        return "guest audio device did not open"
    for key, message in (
        ("audio_callbacks", "guest audio callback did not run"),
        ("audio_nonzero_samples", "guest audio callback produced no nonzero samples"),
        ("audio_callback_entered", "guest audio callback entry count is missing"),
        ("audio_callback_completed", "guest audio callback completion count is missing"),
        ("audio_sample_rate", "guest audio sample rate is missing"),
        ("audio_channels", "guest audio channel count is missing"),
        ("audio_buffer_samples", "guest audio buffer size is missing"),
        ("demo_elapsed_ms", "guest demo elapsed time is missing"),
        ("demo_elapsed_ticks", "guest demo tick span is missing"),
        ("demo_frames", "guest demo frame count is missing"),
    ):
        value = metrics.get(key)
        if value is None or not value.isdecimal() or int(value) < 1:
            return message
    if metrics.get("audio_invalid_callbacks") != "0":
        return "guest audio callback encountered an invalid buffer"
    if metrics["audio_callback_entered"] != metrics["audio_callback_completed"]:
        return "guest audio callback counts differ"
    if metrics.get("audio_audible") != "unverified":
        return "guest audio audibility field is invalid"
    return None


def check_stress_cycles(result_dir, run_id, build_id, count, audio):
    cycles = []
    numeric = ("frames", "ticks", "elapsed_ms", "audio_callbacks_delta",
               "audio_nonzero_delta", "audio_entered_delta", "audio_completed_delta",
               "audio_invalid_delta", "mm_used_memory", "mm_used_blocks",
               "mm_purgable_blocks", "vl_mem_used", "vl_num_surfaces", "avail_mem")
    for number in range(1, count + 1):
        label = f"cycle{number:03d}"
        record = read_record(result_dir / f"{run_id}.{label}")
        error = check_identity(record, run_id, build_id, label)
        if error:
            return error, cycles, None
        if record.get("state") != "finished" or record.get("result") != "pass" or \
           record.get("save_load") != "pass" or record.get("cycle") != str(number):
            return f"invalid {label} completion", cycles, None
        if any(not record.get(key, "").isdecimal() for key in numeric):
            return f"invalid {label} metric", cycles, None
        values = {key: int(record[key]) for key in numeric}
        if any(values[key] == 0 for key in ("frames", "ticks", "elapsed_ms")):
            return f"empty {label} demo", cycles, None
        if values["audio_invalid_delta"] or \
           values["audio_entered_delta"] != values["audio_completed_delta"]:
            return f"invalid {label} audio callback", cycles, None
        if audio and (values["audio_callbacks_delta"] == 0 or
                      values["audio_nonzero_delta"] == 0):
            return f"missing {label} audio", cycles, None
        dump = result_dir / ("actual.dump" if number == 1 else f"{label}.dump")
        save = result_dir / f"{run_id}.save-{number:03d}"
        if not dump.is_file() or dump.stat().st_size != values["frames"] * FRAME_SIZE:
            return f"invalid {label} dump length", cycles, None
        if cycles and values["frames"] != cycles[0]["frames"]:
            return f"{label} frame count differs from first cycle", cycles, None
        with dump.open("rb") as stream:
            first_tick = struct.unpack("<I", stream.read(4))[0]
            stream.seek((values["frames"] - 1) * FRAME_SIZE)
            last_tick = struct.unpack("<I", stream.read(4))[0]
        tick_span = (last_tick - first_tick) & 0xffffffff
        if tick_span != values["ticks"] or (cycles and tick_span != cycles[0]["ticks"]):
            return f"invalid {label} tick span", cycles, None
        if not save.is_file() or save.stat().st_size == 0:
            return f"missing {label} save file", cycles, None
        cycles.append({"cycle": number, "dump_sha256": sha256(dump),
                       "save_sha256": sha256(save), **values})
    warm = cycles[1]
    last = cycles[-1]
    growth = {key: last[key] - warm[key] for key in (
        "mm_used_memory", "mm_used_blocks", "mm_purgable_blocks",
        "vl_mem_used", "vl_num_surfaces", "avail_mem")}
    return None, cycles, growth


def run_once(config, interactive, jit, mode="probe", demo=None,
             variant="release", audible=False, audio=False, cycles=1,
             run_timeout_seconds=0):
    run_id = ("probe-" if mode == "probe" else "game-") + uuid.uuid4().hex[:16]
    executable = ROOT / "build" / "amiga" / (
        "keen-probe" if mode == "probe" else f"{variant}/omnispeak")
    if not executable.is_file():
        raise FileNotFoundError(f"build the executable first: {executable}")
    executable_hash = sha256(executable)
    build_id = executable_hash[:16]
    if mode != "probe":
        failures = validate_game_data(config["game_data"])
        if failures:
            raise ValueError("; ".join(failures))
    reference = None
    if mode in ("replay", "stress"):
        reference = ROOT / "tests" / f"demo{demo}.dump4"
        if not reference.is_file():
            raise FileNotFoundError(f"missing replay reference: {reference}")
        if reference.stat().st_size % FRAME_SIZE:
            raise ValueError(f"incomplete replay reference: {reference}")
    run_dir, guest_command = stage_run(
        config, run_id, build_id, executable, interactive, mode, demo, audible, audio, cycles)
    staged_executable = run_dir / "test" / (
        "keen-probe" if mode == "probe" else "omnispeak")
    if sha256(staged_executable) != executable_hash:
        raise ValueError("executable changed while staging run")
    args = command_for(config, run_dir, jit, audible)
    env = os.environ.copy()
    env["AMIBERRY_HOME_DIR"] = str(run_dir / "home")
    app_info = config["amiberry"].parent.parent / "Info.plist"
    version = None
    if app_info.is_file():
        with app_info.open("rb") as source:
            info = plistlib.load(source)
        version = {
            "short": info.get("CFBundleShortVersionString"),
            "build": info.get("CFBundleVersion"),
        }
    global_ini = Path.home() / "Library" / "Application Support" / "Amiberry" / "amiberry.ini"
    global_ini_hash = None
    if global_ini.is_file():
        shutil.copy2(global_ini, run_dir / "global-amiberry.ini")
        global_ini_hash = sha256(global_ini)
    launch = {
        "run_id": run_id, "build_id": build_id,
        "binary_sha256": executable_hash,
        "rom_sha256": sha256(config["rom"]),
        "emulator_sha256": sha256(config["amiberry"]),
        "emulator_version": version,
        "global_ini_path": str(global_ini),
        "global_ini_sha256": global_ini_hash,
        "args": args, "guest_command": guest_command,
        "environment": {"AMIBERRY_HOME_DIR": env["AMIBERRY_HOME_DIR"]},
        "jit": jit, "cpu": config.get("cpu", "68040"),
        "mode": mode, "demo": demo, "variant": variant if mode != "probe" else None,
        "audible": audible, "audio": audio, "cycles": cycles,
        "run_timeout_seconds": run_timeout_seconds if mode == "run" else None,
    }
    if mode in ("replay", "stress"):
        launch["reference_path"] = str(reference)
        launch["reference_sha256"] = sha256(reference)
    (run_dir / "launch.json").write_text(json.dumps(launch, indent=2) + "\n")
    process = None
    error = None
    start_seconds = None
    total_seconds = 0
    screenshot = "skipped: guest did not reach capture point"
    failure_screenshot = None
    def capture():
        nonlocal screenshot
        screenshot = collect_ipc(process, run_dir)
    try:
        with (run_dir / "host.stdout").open("wb") as stdout, \
             (run_dir / "host.stderr").open("wb") as stderr:
            process = subprocess.Popen(args, stdout=stdout, stderr=stderr, env=env)
            error, start_seconds, total_seconds = wait_for_completion(
                process, run_dir / "results", run_id, build_id, interactive,
                capture, mode, cycles, run_timeout_seconds)
    except OSError as exc:
        error = f"launch failed: {exc}"
    finally:
        if process is not None:
            if error is not None and process.poll() is None:
                failure_screenshot = collect_ipc(process, run_dir, "-failure")
            stop_owned_process(process)
    profile_error = None
    log_path = run_dir / "host.stdout"
    try:
        if log_path.is_file():
            profile_error = check_profile(log_path.read_text(errors="replace"), jit, config.get("cpu", "68040"))
        else:
            profile_error = "missing emulator stdout log"
    except (OSError, ValueError) as exc:
        profile_error = f"cannot inspect emulator log: {exc}"
    if error is None:
        error = profile_error
    comparison = None
    audio_metrics = None
    stress_cycles = None
    memory_growth = None
    try:
        if mode in ("replay", "stress") and error is None:
            actual = run_dir / "results" / "actual.dump"
            if not reference.is_file() or sha256(reference) != launch["reference_sha256"]:
                error = "replay reference changed during run"
            elif not actual.is_file():
                error = "missing replay dump"
            else:
                error, comparison = compare_dumps(actual, reference)
        if mode == "stress" and error is None:
            error, stress_cycles, memory_growth = check_stress_cycles(
                run_dir / "results", run_id, build_id, cycles, audio)
    except (OSError, ValueError, struct.error) as exc:
        error = f"postprocessing failed: {exc}"
    if mode in ("replay", "stress"):
        try:
            final = read_record(run_dir / "results" / f"{run_id}.result")
        except (OSError, ValueError) as exc:
            final = None
            if error is None:
                error = f"invalid guest result: {exc}"
        if final is not None:
            audio_metrics = {key: final.get(key) for key in (
                "audio_opened", "audio_callbacks", "audio_nonzero_samples",
                "audio_callback_entered", "audio_callback_completed",
                "audio_invalid_callbacks",
                "audio_sample_rate", "audio_channels", "audio_buffer_samples",
                "audio_audible", "demo_elapsed_ms", "demo_elapsed_ticks",
                "demo_frames")}
        if error is None and audio:
            error = check_audio_metrics(audio_metrics)
    status = {
        "run_id": run_id, "build_id": build_id,
        "binary_sha256": executable_hash,
        "passed": error is None, "error": error,
        "emulator_pid": process.pid if process else None,
        "emulator_exit_code": process.returncode if process else None,
        "start_seconds": start_seconds, "total_seconds": total_seconds,
        "screenshot": screenshot,
        "failure_screenshot": failure_screenshot,
        "profile_error": profile_error,
        "comparison": comparison,
        "audio_metrics": audio_metrics,
        "stress_cycles": stress_cycles,
        "memory_growth": memory_growth,
    }
    (run_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    return run_dir, status


def regression_cases(repeat, jit, both_jit, audio, both_audio):
    jit_values = (False, True) if both_jit else (jit,)
    audio_values = (False, True) if both_audio else (audio,)
    return [(demo, selected_jit, selected_audio)
            for selected_jit in jit_values
            for selected_audio in audio_values
            for demo in range(5)
            for _ in range(repeat)]


def preflight_regression(config, variant):
    failures = validate_game_data(config["game_data"])
    if failures:
        raise ValueError("; ".join(failures))
    executable = ROOT / "build" / "amiga" / variant / "omnispeak"
    if not executable.is_file():
        raise FileNotFoundError(f"build the executable first: {executable}")
    for demo in range(5):
        reference = ROOT / "tests" / f"demo{demo}.dump4"
        if not reference.is_file() or reference.stat().st_size % FRAME_SIZE:
            raise ValueError(f"missing or incomplete replay reference: {reference}")
    return regression_input_hashes(variant)


def regression_input_hashes(variant):
    return {
        "binary_sha256": sha256(ROOT / "build" / "amiga" / variant / "omnispeak"),
        "reference_sha256": {
            str(demo): sha256(ROOT / "tests" / f"demo{demo}.dump4")
            for demo in range(5)
        },
    }


def write_matrix(path, matrix):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(matrix, indent=2) + "\n")
    temporary.replace(path)


def run_regression(config, repeat, jit, both_jit, audio, both_audio, variant):
    pinned_inputs = preflight_regression(config, variant)
    config["runs_dir"].mkdir(parents=True, exist_ok=True)
    cases = regression_cases(repeat, jit, both_jit, audio, both_audio)
    matrix_id = "regression-" + uuid.uuid4().hex[:16]
    matrix_path = config["runs_dir"] / f"{matrix_id}.json"
    matrix = {
        "matrix_id": matrix_id, "variant": variant,
        "repeat": repeat, "jit_profiles": [False, True] if both_jit else [jit],
        "audio_profiles": [False, True] if both_audio else [audio],
        "binary_sha256": pinned_inputs["binary_sha256"],
        "reference_sha256": pinned_inputs["reference_sha256"],
        "game_data_sha256": {name: sha256(config["game_data"] / name)
                               for name in GAME_HASHES},
        "expected_cases": len(cases), "cases": [], "config_error": None,
    }
    write_matrix(matrix_path, matrix)
    for index, (demo, selected_jit, selected_audio) in enumerate(cases):
        try:
            if regression_input_hashes(variant) != pinned_inputs:
                raise ValueError("regression binary or reference changed")
            run_dir, status = run_once(
                config, False, selected_jit, "replay", demo, variant,
                False, selected_audio)
        except (OSError, ValueError) as exc:
            matrix["config_error"] = str(exc)
            write_matrix(matrix_path, matrix)
            break
        launch = json.loads((run_dir / "launch.json").read_text())
        actual = run_dir / "results" / "actual.dump"
        comparison = status["comparison"] or {}
        actual_hash = comparison.get("actual_sha256")
        actual_hash_error = None
        if actual_hash is None:
            if not actual.is_file():
                actual_hash_error = "missing replay dump"
            else:
                try:
                    actual_hash = sha256(actual)
                except OSError as exc:
                    actual_hash_error = f"cannot hash replay dump: {exc}"
        matrix["cases"].append({
            "demo": demo, "jit": selected_jit, "audio": selected_audio,
            "iteration": index % repeat + 1,
            "run_id": status["run_id"], "build_id": status["build_id"],
            "binary_sha256": status["binary_sha256"],
            "rom_sha256": launch["rom_sha256"],
            "emulator_sha256": launch["emulator_sha256"],
            "global_ini_sha256": launch["global_ini_sha256"],
            "reference_sha256": launch["reference_sha256"],
            "actual_sha256": actual_hash,
            "actual_hash_error": actual_hash_error,
            "run_dir": str(run_dir), "passed": status["passed"] and actual_hash_error is None,
            "error": status["error"] or actual_hash_error, "comparison": status["comparison"],
            "audio_metrics": status["audio_metrics"],
            "status": status,
        })
        if (status["binary_sha256"] != pinned_inputs["binary_sha256"] or
                launch["reference_sha256"] != pinned_inputs["reference_sha256"][str(demo)]):
            matrix["config_error"] = "regression binary or reference changed during run"
            matrix["cases"][-1]["passed"] = False
            matrix["cases"][-1]["error"] = matrix["config_error"]
            write_matrix(matrix_path, matrix)
            break
        write_matrix(matrix_path, matrix)
        print(f"{run_dir}: {'pass' if status['passed'] else status['error']}", flush=True)
    matrix["passed"] = sum(case["passed"] for case in matrix["cases"])
    matrix["failed"] = len(matrix["cases"]) - matrix["passed"]
    matrix["complete"] = matrix["config_error"] is None and len(matrix["cases"]) == len(cases)
    write_matrix(matrix_path, matrix)
    print(matrix_path)
    return 0 if matrix["complete"] and matrix["failed"] == 0 else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("probe", "probe-interactive", "run", "replay", "regression", "stress", "validate-data"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--repeat10", action="store_const", dest="repeat", const=10)
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--run-timeout-seconds", type=int, default=0)
    parser.add_argument("--jit", action="store_true")
    parser.add_argument("--cpu", choices=("68040", "68020"), default="68040")
    parser.add_argument("--demo", type=int, choices=range(5), default=0)
    parser.add_argument("--variant", choices=("release", "debug"), default="release")
    parser.add_argument("--audible", action="store_true")
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--both-jit", action="store_true")
    parser.add_argument("--both-audio", action="store_true")
    args = parser.parse_args()
    if args.repeat < 1 or args.repeat > 100:
        parser.error("--repeat must be between 1 and 100")
    if args.mode in ("run", "probe-interactive") and args.repeat != 1:
        parser.error("interactive run requires --repeat 1")
    if args.audible and args.mode not in ("run", "probe-interactive"):
        parser.error("--audible requires an interactive run")
    if args.audio and args.mode not in ("replay", "regression", "stress"):
        parser.error("--audio requires replay, regression or stress mode")
    if args.mode == "stress" and not 2 <= args.cycles <= 100:
        parser.error("--cycles must be between 2 and 100")
    if args.run_timeout_seconds < 0 or (args.run_timeout_seconds and args.mode != "run"):
        parser.error("--run-timeout-seconds requires run mode and a nonnegative value")
    if (args.both_jit or args.both_audio) and args.mode != "regression":
        parser.error("--both-jit and --both-audio require regression mode")
    if args.cpu == "68020":
        if args.jit or args.both_jit or args.mode.startswith("probe"):
            parser.error("68020 requires a game mode without JIT")
        args.variant += "-68020"
    try:
        config = load_config(args.config)
        config["cpu"] = args.cpu
        if args.mode == "validate-data":
            failures = validate_game_data(config["game_data"])
            if failures:
                print("\n".join(failures), file=sys.stderr)
                return 1
            print("Keen 4 data hashes match")
            return 0
        if args.mode == "regression":
            return run_regression(config, args.repeat, args.jit, args.both_jit,
                                  args.audio, args.both_audio, args.variant)
        config["runs_dir"].mkdir(parents=True, exist_ok=True)
        results = []
        for _ in range(args.repeat):
            run_dir, status = run_once(
                config, args.mode in ("run", "probe-interactive"), args.jit,
                "probe" if args.mode.startswith("probe") else args.mode,
                args.demo, args.variant, args.audible, args.audio,
                args.cycles if args.mode == "stress" else 1,
                args.run_timeout_seconds)
            results.append(status)
            print(f"{run_dir}: {'pass' if status['passed'] else status['error']}", flush=True)
        summary = {
            "mode": args.mode, "jit": args.jit, "repeat": args.repeat,
            "passed": sum(item["passed"] for item in results),
            "runs": [item["run_id"] for item in results],
            "start_seconds": [item["start_seconds"] for item in results],
            "total_seconds": [item["total_seconds"] for item in results],
        }
        starts = [value for value in summary["start_seconds"] if value is not None]
        if starts:
            summary["median_start_seconds"] = statistics.median(starts)
        summary["median_total_seconds"] = statistics.median(summary["total_seconds"])
        print(json.dumps(summary, indent=2))
        return 0 if summary["passed"] == args.repeat else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
