import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from jarvis_assistant.audio import audio_levels
from jarvis_assistant.speech import (
    TextToSpeech,
    WhisperTranscriber,
    _looks_like_cuda_load_failure,
    best_available_voice_name,
    clean_transcription_text,
    list_piper_voices,
    list_speech_output_devices,
    smooth_text_for_speech,
)
from jarvis_assistant.speech_diagnostics import run_speech_diagnostics


class SpeechTests(unittest.TestCase):
    def test_cuda_dll_error_is_detected(self):
        self.assertTrue(_looks_like_cuda_load_failure(RuntimeError("Library cublas64_12.dll is not found")))

    def test_cuda_failure_falls_back_to_cpu_int8(self):
        fake_model = MagicMock(side_effect=[RuntimeError("cublas64_12.dll is not found"), object()])

        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=fake_model)}):
            transcriber = WhisperTranscriber("tiny", "cuda", "float16")

        self.assertEqual(transcriber.active_device, "cpu")
        self.assertEqual(transcriber.active_compute_type, "int8")
        self.assertIn("fell back", transcriber.status_message)
        self.assertEqual(fake_model.call_args_list[-1].kwargs["device"], "cpu")

    def test_missing_preferred_model_falls_back_to_base(self):
        fake_model = MagicMock(side_effect=[RuntimeError("network unavailable"), object()])

        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=fake_model)}):
            transcriber = WhisperTranscriber("small", "cpu", "int8")

        self.assertEqual(transcriber.active_model, "base")
        self.assertIn("fell back to base", transcriber.status_message)
        self.assertEqual(fake_model.call_args_list[-1].args[0], "base")

    def test_whisper_transcriber_defaults_to_fast_beam_for_wake_checks(self):
        fake_model = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=fake_model)}):
            transcriber = WhisperTranscriber("tiny", "cpu", "int8")

        self.assertEqual(transcriber.beam_size, 1)

    def test_whisper_transcriber_uses_accuracy_oriented_options(self):
        segment = MagicMock()
        segment.text = " open apex legend "
        fake_instance = MagicMock()
        fake_instance.transcribe.return_value = ([segment], object())
        fake_model = MagicMock(return_value=fake_instance)

        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=fake_model)}):
            transcriber = WhisperTranscriber("small", "cpu", "int8", beam_size=5)
            text = transcriber.transcribe(Path("sample.wav"))

        self.assertEqual(text, "open Apex Legends")
        fake_instance.transcribe.assert_called_once()
        kwargs = fake_instance.transcribe.call_args.kwargs
        self.assertEqual(kwargs["language"], "en")
        self.assertEqual(kwargs["beam_size"], 5)
        self.assertFalse(kwargs["condition_on_previous_text"])
        self.assertIn("Damien", kwargs["initial_prompt"])

    def test_clean_transcription_text_removes_common_whisper_noise(self):
        self.assertEqual(clean_transcription_text("Thanks for watching."), "")
        self.assertEqual(clean_transcription_text("hey day mien open settings"), "hey Damien open settings")
        self.assertEqual(clean_transcription_text("hey Damon open roll blocks studio"), "hey Damien open Roblox Studio")

    def test_speech_diagnostics_reports_project_venv(self):
        with patch("jarvis_assistant.speech_diagnostics.sys.executable", r"C:\Project\.venv\Scripts\python.exe"):
            with patch("jarvis_assistant.speech_diagnostics._can_import", return_value=False):
                diagnostics = run_speech_diagnostics()

        self.assertTrue(diagnostics.running_from_venv)

    def test_audio_levels_report_silence_and_volume(self):
        silent_rms, silent_peak, silent_percent = audio_levels(np.zeros((4, 1), dtype=np.int16))
        loud_rms, loud_peak, loud_percent = audio_levels(np.array([[0], [16000], [-16000]], dtype=np.int16))

        self.assertEqual((silent_rms, silent_peak, silent_percent), (0.0, 0.0, 0))
        self.assertGreater(loud_rms, 0)
        self.assertGreater(loud_peak, 0)
        self.assertGreater(loud_percent, 0)

    def test_speech_output_devices_returns_empty_when_sapi_unavailable(self):
        with patch("jarvis_assistant.speech._speech_output_category", side_effect=RuntimeError("no sapi")):
            self.assertEqual(list_speech_output_devices(), [])

    def test_text_to_speech_stores_selected_output_device(self):
        fake_pyttsx3 = MagicMock()
        with patch.dict("sys.modules", {"pyttsx3": fake_pyttsx3}):
            tts = TextToSpeech("Headphones", "Microsoft Zira Desktop", 165, 0.9)

        self.assertEqual(tts.output_device_name, "Headphones")
        self.assertEqual(tts.voice_name, "Microsoft Zira Desktop")
        self.assertEqual(tts.rate, 165)
        self.assertEqual(tts.volume, 0.9)
        self.assertEqual(tts.engine_name, TextToSpeech.ENGINE_PIPER)

    def test_list_piper_voices_reads_packaged_voice_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            voice_dir = Path(temp_dir) / "assets" / "voices"
            voice_dir.mkdir(parents=True)
            (voice_dir / "en_US-ryan-high.onnx").write_bytes(b"voice")

            with patch("jarvis_assistant.speech.APP_ROOT", Path(temp_dir)):
                self.assertEqual(list_piper_voices(), ["en_US-ryan-high"])

    def test_best_available_voice_prefers_male_windows_voice(self):
        voice = best_available_voice_name([
            "Microsoft David Desktop - English (United States)",
            "Microsoft Zira Desktop - English (United States)",
        ])

        self.assertEqual(voice, "Microsoft David Desktop - English (United States)")

    def test_smooth_text_for_speech_removes_markdown_and_softens_phrasing(self):
        spoken = smooth_text_for_speech("I am ready - `open chrome`\n- I will help. Do not worry.")

        self.assertEqual(spoken, "I'm ready. open chrome I'll help. Don't worry.")

    def test_smooth_text_for_speech_strips_markdown_markers_before_tts(self):
        spoken = smooth_text_for_speech(
            "1. **Windows basics**: I will help.\n"
            "2. __Discord calls__: [Open Discord](discord://-/channels/@me/123).\n"
            "> *Do not* say the symbol name."
        )

        self.assertNotIn("*", spoken)
        self.assertNotIn("_", spoken)
        self.assertNotIn("[", spoken)
        self.assertNotIn("]", spoken)
        self.assertEqual(spoken, "Windows basics: I'll help. Discord calls: Open Discord. Don't say the symbol name.")


if __name__ == "__main__":
    unittest.main()
