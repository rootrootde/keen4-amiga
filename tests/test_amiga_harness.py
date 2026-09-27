from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "amiga-test.py"
SPEC = importlib.util.spec_from_file_location("amiga_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.results = Path(self.temp.name)
        self.run_id = "probe-current"
        self.build_id = "abc123"

    def write(self, name, content):
        (self.results / name).write_text(content)

    def complete(self):
        prefix = f"run_id={self.run_id}\nbuild_id={self.build_id}\n"
        self.write(f"{self.run_id}.start", prefix + "state=started\n")
        self.write(f"{self.run_id}.result", prefix + "state=finished\nresult=pass\n")
        self.write("returned", prefix)

    def test_complete_run(self):
        self.complete()
        self.assertIsNone(MODULE.verify_completion(self.results, self.run_id, self.build_id))

    def test_missing_completion(self):
        self.complete()
        (self.results / "returned").unlink()
        self.assertEqual(MODULE.verify_completion(self.results, self.run_id, self.build_id),
                         "missing returned")

    def test_wrong_build_id(self):
        self.complete()
        self.write("returned", f"run_id={self.run_id}\nbuild_id=old\n")
        self.assertEqual(MODULE.verify_completion(self.results, self.run_id, self.build_id),
                         "returned has wrong run or build ID")

    def test_stale_result_state(self):
        self.complete()
        self.write(f"{self.run_id}.result",
                   f"run_id={self.run_id}\nbuild_id={self.build_id}\nstate=started\nresult=pass\n")
        self.assertEqual(MODULE.verify_completion(self.results, self.run_id, self.build_id),
                         "result has wrong state")

    def test_guest_failure(self):
        self.complete()
        self.write(f"{self.run_id}.result",
                   f"run_id={self.run_id}\nbuild_id={self.build_id}\nstate=finished\nresult=fail\n")
        self.assertEqual(MODULE.verify_completion(self.results, self.run_id, self.build_id),
                         "guest result is not pass")

    def test_start_timeout(self):
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(MODULE, "START_TIMEOUT", 1), \
             mock.patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 2]), \
             mock.patch.object(MODULE.time, "sleep"):
            error, started, _ = MODULE.wait_for_completion(
                process, self.results, self.run_id, self.build_id, False)
        self.assertEqual(error, "start timeout")
        self.assertIsNone(started)

    def test_final_timeout(self):
        self.write(f"{self.run_id}.start",
                   f"run_id={self.run_id}\nbuild_id={self.build_id}\nstate=started\n")
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 1, 100]), \
             mock.patch.object(MODULE.time, "sleep"):
            error, started, _ = MODULE.wait_for_completion(
                process, self.results, self.run_id, self.build_id, False)
        self.assertEqual(error, "final timeout")
        self.assertEqual(started, 1)

    def test_manual_run_can_exceed_ten_minutes(self):
        self.write(f"{self.run_id}.start",
                   f"run_id={self.run_id}\nbuild_id={self.build_id}\nstate=started\n")
        process = mock.Mock()
        process.poll.return_value = None
        def complete(_):
            self.complete()
        with mock.patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 1, 700]), \
             mock.patch.object(MODULE.time, "sleep", side_effect=complete):
            error, started, _ = MODULE.wait_for_completion(
                process, self.results, self.run_id, self.build_id, True,
                mode="run")
        self.assertIsNone(error)
        self.assertEqual(started, 1)

    def test_manual_run_explicit_timeout(self):
        self.write(f"{self.run_id}.start",
                   f"run_id={self.run_id}\nbuild_id={self.build_id}\nstate=started\n")
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 1, 11]), \
             mock.patch.object(MODULE.time, "sleep"):
            error, _, _ = MODULE.wait_for_completion(
                process, self.results, self.run_id, self.build_id, True,
                mode="run", run_timeout_seconds=10)
        self.assertEqual(error, "final timeout")

    def test_partial_start_is_not_rejected(self):
        self.write(f"{self.run_id}.start", f"run_id={self.run_id}\n")
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(MODULE, "START_TIMEOUT", 1), \
             mock.patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 2]), \
             mock.patch.object(MODULE.time, "sleep"):
            error, _, _ = MODULE.wait_for_completion(
                process, self.results, self.run_id, self.build_id, False)
        self.assertEqual(error, "start timeout")

    def test_final_is_read_after_return_marker(self):
        self.write(f"{self.run_id}.start",
                   f"run_id={self.run_id}\nbuild_id={self.build_id}\nstate=started\n")
        self.write(f"{self.run_id}.result", "incomplete\n")
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 1, 100]), \
             mock.patch.object(MODULE.time, "sleep"):
            error, _, _ = MODULE.wait_for_completion(
                process, self.results, self.run_id, self.build_id, False)
        self.assertEqual(error, "final timeout")

    def test_stress_is_not_limited_to_probe_deadline(self):
        self.write(f"{self.run_id}.start",
                   f"run_id={self.run_id}\nbuild_id={self.build_id}\nstate=started\n")
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 1, 50, 602]), \
             mock.patch.object(MODULE.time, "sleep"):
            error, _, _ = MODULE.wait_for_completion(
                process, self.results, self.run_id, self.build_id, False,
                mode="stress", cycles=3)
        self.assertEqual(error, "stress cycle timeout")

    def test_stress_deadline_resets_at_completed_cycle(self):
        self.write(f"{self.run_id}.start",
                   f"run_id={self.run_id}\nbuild_id={self.build_id}\nstate=started\n")
        process = mock.Mock()
        process.poll.return_value = None
        def publish_cycle(_):
            if not (self.results / f"{self.run_id}.cycle001").exists():
                self.write(f"{self.run_id}.cycle001",
                           f"run_id={self.run_id}\nbuild_id={self.build_id}\n"
                           "state=finished\nresult=pass\n")
        with mock.patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 1, 550, 700, 1151]), \
             mock.patch.object(MODULE.time, "sleep", side_effect=publish_cycle):
            error, _, _ = MODULE.wait_for_completion(
                process, self.results, self.run_id, self.build_id, False,
                mode="stress", cycles=3)
        self.assertEqual(error, "stress cycle timeout")


class GameDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name)

    def test_missing_files(self):
        self.assertEqual(MODULE.validate_game_data(self.game),
                         [f"missing {name}" for name in MODULE.GAME_HASHES])

    def test_wrong_hash(self):
        for name in MODULE.GAME_HASHES:
            (self.game / name).write_bytes(b"wrong")
        self.assertEqual(MODULE.validate_game_data(self.game),
                         [f"hash mismatch {name}" for name in MODULE.GAME_HASHES])


class IpcOwnershipTests(unittest.TestCase):
    def test_matching_socket_owner(self):
        result = mock.Mock(returncode=0, stdout="p123\nn/tmp/amiberry.sock\n")
        with mock.patch.object(MODULE.subprocess, "run", return_value=result):
            self.assertTrue(MODULE.owns_ipc_socket(123, "/tmp/amiberry.sock"))

    def test_other_socket_is_not_owned(self):
        result = mock.Mock(returncode=0, stdout="p123\nn/tmp/other.sock\n")
        with mock.patch.object(MODULE.subprocess, "run", return_value=result):
            self.assertFalse(MODULE.owns_ipc_socket(123, "/tmp/amiberry.sock"))


class ProfileTests(unittest.TestCase):
    def test_enabled_profile(self):
        log = ("JIT: <JIT compiler> : actual translation cache size : 8192 KB\n"
               "CPU=68040, FPU=68040, JIT=CPU/FPU=8192. fast\n")
        self.assertIsNone(MODULE.check_profile(log, True))

    def test_requested_jit_but_disabled(self):
        log = "JIT: cache=0. b=1\nCPU=68040, FPU=68040, JIT=0. fast\n"
        self.assertIn("effective JIT profile", MODULE.check_profile(log, True))


class ReplayComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.actual = self.root / "actual"
        self.reference = self.root / "reference"
        self.frame = bytes(MODULE.FRAME_SIZE)

    def compare(self, actual, reference):
        self.actual.write_bytes(actual)
        self.reference.write_bytes(reference)
        return MODULE.compare_dumps(self.actual, self.reference)

    def test_exact_match(self):
        error, detail = self.compare(self.frame * 2, self.frame * 2)
        self.assertIsNone(error)
        self.assertEqual(detail["frames"], 2)

    def test_first_tick_mismatch(self):
        actual = bytearray(self.frame * 2)
        actual[MODULE.FRAME_SIZE + 2] = 1
        error, detail = self.compare(actual, self.frame * 2)
        self.assertEqual(error, "first mismatch at frame 1, tick offset 2 (expected tick 0, actual tick 65536)")
        self.assertEqual(detail["offset"], MODULE.FRAME_SIZE + 2)

    def test_object_mismatch(self):
        actual = bytearray(self.frame)
        actual[90 + 76 * 4 + 3] = 7
        error, detail = self.compare(actual, self.frame)
        self.assertEqual(error, "first mismatch at frame 0, object 4 offset 3 (expected tick 0, actual tick 0)")
        self.assertEqual((detail["expected_tick"], detail["actual_tick"]), (0, 0))

    def test_state_mismatch_reports_both_ticks(self):
        actual = bytearray(self.frame)
        actual[4 + 5] = 3
        error, detail = self.compare(actual, self.frame)
        self.assertEqual(error, "first mismatch at frame 0, game state offset 5 (expected tick 0, actual tick 0)")
        self.assertEqual((detail["expected_tick"], detail["actual_tick"]), (0, 0))

    def test_truncated_dump(self):
        error, _ = self.compare(self.frame[:-1], self.frame)
        self.assertEqual(error, "dump has incomplete frame")

    def test_missing_complete_frame(self):
        error, _ = self.compare(self.frame, self.frame * 2)
        self.assertEqual(error, "dump length differs from reference")

    def test_bad_reference(self):
        error, _ = self.compare(self.frame, self.frame[:-1])
        self.assertEqual(error, "reference has incomplete frame")


class EngineStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.system = self.root / "system"
        self.system.mkdir()
        self.game = self.root / "game"
        self.game.mkdir()
        for name in MODULE.GAME_HASHES:
            (self.game / name).write_bytes(name.encode())
        self.executable = self.root / "omnispeak"
        self.executable.write_bytes(b"binary")
        self.config = {
            "runs_dir": self.root / "runs", "system_base": self.system,
            "game_data": self.game,
        }
        self.config["runs_dir"].mkdir()

    def test_replay_stages_copies_and_ids(self):
        run, command = MODULE.stage_run(
            self.config, "game-123", "build-456", self.executable,
            False, "replay", 3)
        self.assertIn("/RUNID game-123 /BUILDID build-456", command)
        self.assertIn("/AUTOTEST", command)
        self.assertIn("/NOSOUND /PLAYDEMO 3 /DUMPFILE RESULT:actual.dump", command)
        self.assertEqual((run / "test" / "AUDIO.CK4").read_bytes(), b"AUDIO.CK4")
        self.assertEqual((self.game / "AUDIO.CK4").read_bytes(), b"AUDIO.CK4")
        self.assertTrue((run / "test" / "EPISODE.CK4").is_file())
        self.assertIn("CD TEST:\n", (run / "test" / "run-test").read_text())

    def test_audio_replay_keeps_guest_sound_enabled(self):
        _, command = MODULE.stage_run(
            self.config, "game-audio", "build-456", self.executable,
            False, "replay", 0, audio=True)
        self.assertNotIn("/NOSOUND", command)
        self.assertIn("/AUTOTEST", command)
        self.assertIn("/PLAYDEMO 0", command)

    def test_stress_stages_one_process_with_autotest(self):
        _, command = MODULE.stage_run(
            self.config, "game-stress", "build-456", self.executable,
            False, "stress", 0, audio=True, cycles=20)
        self.assertIn("/AUTOTEST /PLAYDEMO 0 /DUMPFILE RESULT:actual.dump /STRESS 20", command)
        self.assertNotIn("/NOSOUND", command)

    def test_stress_cycle_records_and_memory_growth(self):
        result = self.root / "stress-results"
        result.mkdir()
        for number in range(1, 4):
            fields = {
                "run_id": "game-stress", "build_id": "build-456",
                "state": "finished", "result": "pass", "save_load": "pass",
                "cycle": str(number), "frames": "2", "ticks": "3", "elapsed_ms": "4",
                "audio_callbacks_delta": "5", "audio_nonzero_delta": "6",
                "audio_entered_delta": "5", "audio_completed_delta": "5",
                "audio_invalid_delta": "0", "mm_used_memory": str(100 + number),
                "mm_used_blocks": "8", "mm_purgable_blocks": "1",
                "vl_mem_used": "20", "vl_num_surfaces": "2", "avail_mem": "1000",
            }
            (result / f"game-stress.cycle{number:03d}").write_text(
                "".join(f"{key}={value}\n" for key, value in fields.items()))
            dump_name = "actual.dump" if number == 1 else f"cycle{number:03d}.dump"
            dump = bytearray(2 * MODULE.FRAME_SIZE)
            struct.pack_into("<I", dump, 0, 10)
            struct.pack_into("<I", dump, MODULE.FRAME_SIZE, 13)
            (result / dump_name).write_bytes(dump)
            (result / f"game-stress.save-{number:03d}").write_bytes(b"save")
        error, cycles, growth = MODULE.check_stress_cycles(
            result, "game-stress", "build-456", 3, True)
        self.assertIsNone(error)
        self.assertEqual(len(cycles), 3)
        self.assertEqual(growth["mm_used_memory"], 1)
        (result / "cycle003.dump").write_bytes(b"x")
        error, _, _ = MODULE.check_stress_cycles(
            result, "game-stress", "build-456", 3, True)
        self.assertEqual(error, "invalid cycle003 dump length")

    def test_later_cycle_needs_first_frame_count(self):
        self.test_stress_cycle_records_and_memory_growth()
        result = self.root / "stress-results"
        record = result / "game-stress.cycle003"
        record.write_text(record.read_text().replace("frames=2\n", "frames=1\n"))
        (result / "cycle003.dump").write_bytes((result / "actual.dump").read_bytes()[:MODULE.FRAME_SIZE])
        error, _, _ = MODULE.check_stress_cycles(
            result, "game-stress", "build-456", 3, True)
        self.assertEqual(error, "cycle003 frame count differs from first cycle")

    def test_interactive_runs_do_not_disable_input(self):
        _, game_command = MODULE.stage_run(
            self.config, "game-interactive", "build-456", self.executable,
            True, "run")
        _, probe_command = MODULE.stage_run(
            self.config, "probe-interactive", "build-456", self.executable,
            True, "probe")
        self.assertNotIn("/AUTOTEST", game_command)
        self.assertNotIn("/AUTOTEST", probe_command)

    def test_host_audio_muted_unless_requested(self):
        config = {"amiberry": Path("/tmp/amiberry"), "rom": Path("/tmp/rom")}
        command = MODULE.command_for(config, self.root, False)
        self.assertIn("sound_volume=100", command)
        self.assertIn("sound_output=normal", command)
        audible = MODULE.command_for(config, self.root, False, True)
        self.assertIn("sound_volume=0", audible)


class RunPostprocessingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runs = self.root / "runs"
        self.runs.mkdir()
        system = self.root / "system"
        system.mkdir()
        game = self.root / "game"
        game.mkdir()
        for name in MODULE.GAME_HASHES:
            (game / name).write_bytes(name.encode())
        support = self.root / "data" / "keen4"
        support.mkdir(parents=True)
        (support / "EPISODE.CK4").write_bytes(b"support")
        binary = self.root / "build" / "amiga" / "release" / "omnispeak"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"binary")
        reference = self.root / "tests" / "demo0.dump4"
        reference.parent.mkdir()
        reference.write_bytes(bytes(MODULE.FRAME_SIZE))
        emulator = self.root / "emulator" / "amiberry"
        emulator.parent.mkdir()
        emulator.write_bytes(b"emulator")
        rom = self.root / "rom"
        rom.write_bytes(b"rom")
        self.config = {"runs_dir": self.runs, "system_base": system,
                       "game_data": game, "amiberry": emulator, "rom": rom}

    def run_with_failure(self, mode, failing_function, exception):
        process = mock.Mock(pid=123, returncode=0)
        process.poll.return_value = 0
        def completed(*_args, **_kwargs):
            run_dir, = self.runs.iterdir()
            (run_dir / "results" / "actual.dump").write_bytes(bytes(MODULE.FRAME_SIZE))
            return None, 1, 2
        patches = [
            mock.patch.object(MODULE, "ROOT", self.root),
            mock.patch.object(MODULE, "validate_game_data", return_value=[]),
            mock.patch.object(MODULE, "command_for", return_value=["emulator"]),
            mock.patch.object(MODULE.subprocess, "Popen", return_value=process),
            mock.patch.object(MODULE, "wait_for_completion", side_effect=completed),
            mock.patch.object(MODULE, "check_profile", return_value=None),
            mock.patch.object(MODULE, "stop_owned_process"),
            mock.patch.object(MODULE, failing_function, side_effect=exception),
        ]
        with patches[0], patches[1], patches[2], patches[3], \
             patches[4], patches[5], patches[6], patches[7]:
            return MODULE.run_once(self.config, False, False, mode, 0,
                                   audio=False, cycles=2 if mode == "stress" else 1)

    def test_dump_read_failure_writes_failed_status(self):
        run_dir, status = self.run_with_failure("replay", "compare_dumps",
                                                OSError("dump unavailable"))
        self.assertFalse(status["passed"])
        self.assertEqual(status["error"], "postprocessing failed: dump unavailable")
        self.assertEqual(MODULE.json.loads((run_dir / "status.json").read_text()), status)

    def test_bad_stress_record_writes_failed_status(self):
        with mock.patch.object(MODULE, "compare_dumps", return_value=(None, {"frames": 1})):
            run_dir, status = self.run_with_failure("stress", "check_stress_cycles",
                                                    ValueError("duplicate cycle field"))
        self.assertFalse(status["passed"])
        self.assertEqual(status["error"], "postprocessing failed: duplicate cycle field")
        self.assertEqual(MODULE.json.loads((run_dir / "status.json").read_text()), status)


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runs = Path(self.temp.name) / "runs"
        game = Path(self.temp.name) / "game"
        game.mkdir()
        for name in MODULE.GAME_HASHES:
            (game / name).write_bytes(name.encode())
        self.config = {"runs_dir": self.runs, "game_data": game}
        self.pinned = {
            "binary_sha256": "binary",
            "reference_sha256": {str(demo): "reference" for demo in range(5)},
        }

    def test_case_counts_and_order(self):
        for repeat, both_jit, both_audio, expected in (
            (1, False, False, 5),
            (2, False, False, 10),
            (1, True, False, 10),
            (1, False, True, 10),
            (2, True, True, 40),
        ):
            cases = MODULE.regression_cases(repeat, False, both_jit,
                                            False, both_audio)
            self.assertEqual(len(cases), expected)
            self.assertEqual(cases[:repeat], [(0, False, False)] * repeat)
            self.assertEqual({case[0] for case in cases}, set(range(5)))
            self.assertEqual({case[1] for case in cases},
                             {False, True} if both_jit else {False})
            self.assertEqual({case[2] for case in cases},
                             {False, True} if both_audio else {False})
        self.assertEqual(MODULE.regression_cases(1, True, False, True, False),
                         [(demo, True, True) for demo in range(5)])

    def test_matrix_records_each_run_and_continues_after_failure(self):
        calls = []

        def fake_run(config, interactive, jit, mode, demo, variant,
                     audible, audio):
            self.assertEqual((interactive, mode, variant, audible),
                             (False, "replay", "release", False))
            run_id = f"game-{len(calls)}"
            calls.append((demo, jit, audio))
            run_dir = self.runs / run_id
            (run_dir / "results").mkdir(parents=True)
            actual = run_dir / "results" / "actual.dump"
            actual.write_bytes(run_id.encode())
            launch = {
                "rom_sha256": "rom", "emulator_sha256": "emulator",
                "global_ini_sha256": None, "reference_sha256": "reference",
            }
            (run_dir / "launch.json").write_text(MODULE.json.dumps(launch))
            failed = demo == 2
            status = {
                "run_id": run_id, "build_id": "build",
                "binary_sha256": "binary", "passed": not failed,
                "error": "dump mismatch" if failed else None,
                "comparison": {"frames": 1}, "audio_metrics": None,
            }
            return run_dir, status

        with mock.patch.object(MODULE, "preflight_regression", return_value=self.pinned), \
             mock.patch.object(MODULE, "regression_input_hashes", return_value=self.pinned), \
             mock.patch.object(MODULE, "run_once", side_effect=fake_run), \
             redirect_stdout(io.StringIO()):
            exit_code = MODULE.run_regression(self.config, 2, False, True,
                                              False, True, "release")

        self.assertEqual(exit_code, 1)
        self.assertEqual(calls, MODULE.regression_cases(2, False, True,
                                                       False, True))
        matrices = list(self.runs.glob("regression-*.json"))
        self.assertEqual(len(matrices), 1)
        matrix = MODULE.json.loads(matrices[0].read_text())
        self.assertTrue(matrix["complete"])
        self.assertEqual((matrix["expected_cases"], matrix["passed"],
                          matrix["failed"]), (40, 32, 8))
        self.assertEqual(matrix["game_data_sha256"], {
            name: MODULE.hashlib.sha256(name.encode()).hexdigest()
            for name in MODULE.GAME_HASHES})
        self.assertEqual(matrix["binary_sha256"], "binary")
        self.assertEqual(matrix["reference_sha256"], self.pinned["reference_sha256"])
        self.assertEqual([case["iteration"] for case in matrix["cases"][:4]],
                         [1, 2, 1, 2])
        for index, case in enumerate(matrix["cases"]):
            self.assertEqual(case["run_id"], f"game-{index}")
            self.assertEqual(case["build_id"], "build")
            self.assertEqual(case["binary_sha256"], "binary")
            self.assertEqual(case["rom_sha256"], "rom")
            self.assertEqual(case["emulator_sha256"], "emulator")
            self.assertEqual(case["reference_sha256"], "reference")
            self.assertEqual(case["actual_sha256"], MODULE.hashlib.sha256(
                f"game-{index}".encode()).hexdigest())
            self.assertEqual(case["passed"], case["demo"] != 2)
            self.assertEqual(case["status"]["error"], case["error"])

    def test_changed_input_stops_before_next_case(self):
        changed = {
            "binary_sha256": "new binary",
            "reference_sha256": self.pinned["reference_sha256"],
        }
        with mock.patch.object(MODULE, "preflight_regression", return_value=self.pinned), \
             mock.patch.object(MODULE, "regression_input_hashes", return_value=changed), \
             mock.patch.object(MODULE, "run_once") as run, \
             redirect_stdout(io.StringIO()):
            exit_code = MODULE.run_regression(self.config, 1, False, False,
                                              False, False, "release")
        self.assertEqual(exit_code, 1)
        run.assert_not_called()
        matrix_path, = self.runs.glob("regression-*.json")
        matrix = MODULE.json.loads(matrix_path.read_text())
        self.assertFalse(matrix["complete"])
        self.assertEqual(matrix["config_error"],
                         "regression binary or reference changed")

    def test_unreadable_failed_dump_keeps_matrix_case(self):
        def fake_run(_config, _interactive, _jit, _mode, demo, _variant,
                     _audible, _audio):
            run_id = f"game-{demo}"
            run_dir = self.runs / run_id
            (run_dir / "results").mkdir(parents=True)
            (run_dir / "results" / "actual.dump").write_bytes(b"dump")
            launch = {"rom_sha256": "rom", "emulator_sha256": "emulator",
                      "global_ini_sha256": None, "reference_sha256": "reference"}
            (run_dir / "launch.json").write_text(MODULE.json.dumps(launch))
            failed = demo == 2
            status = {"run_id": run_id, "build_id": "build", "binary_sha256": "binary",
                      "passed": not failed, "error": "dump read failed" if failed else None,
                      "comparison": None, "audio_metrics": None}
            return run_dir, status

        real_sha256 = MODULE.sha256
        def maybe_unreadable(path):
            if path.name == "actual.dump" and path.parent.parent.name == "game-2":
                raise OSError("permission denied")
            return real_sha256(path)

        with mock.patch.object(MODULE, "preflight_regression", return_value=self.pinned), \
             mock.patch.object(MODULE, "regression_input_hashes", return_value=self.pinned), \
             mock.patch.object(MODULE, "run_once", side_effect=fake_run), \
             mock.patch.object(MODULE, "sha256", side_effect=maybe_unreadable), \
             redirect_stdout(io.StringIO()):
            code = MODULE.run_regression(self.config, 1, False, False,
                                         False, False, "release")
        self.assertEqual(code, 1)
        matrix_path, = self.runs.glob("regression-*.json")
        matrix = MODULE.json.loads(matrix_path.read_text())
        self.assertTrue(matrix["complete"])
        self.assertIsNone(matrix["config_error"])
        self.assertEqual(len(matrix["cases"]), 5)
        failed = matrix["cases"][2]
        self.assertFalse(failed["passed"])
        self.assertEqual(failed["error"], "dump read failed")
        self.assertIsNone(failed["actual_sha256"])
        self.assertEqual(failed["actual_hash_error"],
                         "cannot hash replay dump: permission denied")


class AudioMetricTests(unittest.TestCase):
    def test_valid_muted_audio_metrics(self):
        metrics = {
            "audio_opened": "1", "audio_callbacks": "170",
            "audio_nonzero_samples": "4300", "audio_audible": "unverified",
            "audio_callback_entered": "170", "audio_callback_completed": "170",
            "audio_invalid_callbacks": "0",
            "audio_sample_rate": "22050", "audio_channels": "1",
            "audio_buffer_samples": "512",
            "demo_elapsed_ms": "28000", "demo_elapsed_ticks": "2200",
            "demo_frames": "812",
        }
        self.assertIsNone(MODULE.check_audio_metrics(metrics))
        metrics["audio_nonzero_samples"] = "0"
        self.assertEqual(MODULE.check_audio_metrics(metrics),
                         "guest audio callback produced no nonzero samples")
        metrics["audio_nonzero_samples"] = "4300"
        metrics.pop("audio_sample_rate")
        self.assertEqual(MODULE.check_audio_metrics(metrics),
                         "guest audio sample rate is missing")

    def test_invalid_callback_fails(self):
        metrics = {
            "audio_opened": "1", "audio_callbacks": "2",
            "audio_nonzero_samples": "1", "audio_audible": "unverified",
            "audio_callback_entered": "3", "audio_callback_completed": "2",
            "audio_invalid_callbacks": "1", "demo_elapsed_ms": "1",
            "audio_sample_rate": "22050", "audio_channels": "1",
            "audio_buffer_samples": "512",
            "demo_elapsed_ticks": "1", "demo_frames": "1",
        }
        self.assertEqual(MODULE.check_audio_metrics(metrics),
                         "guest audio callback encountered an invalid buffer")

    def test_missing_audio_metrics(self):
        self.assertEqual(MODULE.check_audio_metrics(None),
                         "guest audio device did not open")


if __name__ == "__main__":
    unittest.main()
