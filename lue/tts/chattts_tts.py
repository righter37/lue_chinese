"""ChatTTS TTS backend for the Lue eBook reader.

ChatTTS runs locally in the same process as lue (no separate server needed).
Install with: pip install ChatTTS soundfile

The model (~1 GB) is downloaded automatically from HuggingFace on first use.
"""

import asyncio
import logging
import os
import tempfile
from rich.console import Console

from .base import TTSBase


class ChatttsTTS(TTSBase):
    """TTS implementation using ChatTTS local model."""

    @property
    def name(self) -> str:
        return "chattts"

    @property
    def output_format(self) -> str:
        return "wav"

    def get_overlap_seconds(self) -> float:
        """ChatTTS generates audio faster than GPT-SoVITS; use small overlap."""
        return 0.2

    def __init__(self, console: Console, voice: str = None, lang: str = None):
        super().__init__(console, voice, lang)
        self._chat = None
        self._speaker = None

    async def initialize(self) -> bool:
        """Load the ChatTTS model (runs in thread to avoid blocking event loop)."""
        try:
            import ChatTTS  # noqa: F401
        except ImportError:
            self.console.print(
                "[bold red]ChatTTS not installed.[/bold red] "
                "Run inside WSL: [yellow]pip install ChatTTS soundfile[/yellow]"
            )
            return False

        self.console.print("[bold cyan]Loading ChatTTS model (first run downloads ~1 GB)…[/bold cyan]")
        try:
            await asyncio.to_thread(self._load_model)
            self.initialized = True
            self.console.print("[green]ChatTTS model loaded.[/green]")
            return True
        except Exception as e:
            self.console.print(f"[bold red]Failed to load ChatTTS: {e}[/bold red]")
            logging.error("ChatTTS initialization failed", exc_info=True)
            return False

    def _load_model(self):
        import ChatTTS
        self._chat = ChatTTS.Chat()
        self._chat.load(compile=False)
        # Sample a fixed speaker embedding so voice stays consistent across sentences.
        self._speaker = self._chat.sample_random_speaker()

    async def generate_audio(self, text: str, output_path: str):
        """Synthesize speech and write to output_path (WAV, 24 kHz)."""
        if not self.initialized or self._chat is None:
            raise RuntimeError("ChatTTS has not been initialized.")

        await asyncio.to_thread(self._infer, text, output_path)

    def _infer(self, text: str, output_path: str):
        import soundfile as sf

        params = self._chat.InferCodeParams(
            spk_emb=self._speaker,
            temperature=0.3,
            top_P=0.7,
            top_K=20,
        )
        wavs = self._chat.infer([text], params_infer_code=params, use_decoder=True)
        audio = wavs[0]

        # ChatTTS returns float32 numpy arrays at 24 kHz.
        sf.write(output_path, audio, samplerate=24000)

    async def warm_up(self):
        """Send a short test phrase to warm up the model."""
        if not self.initialized:
            return
        self.console.print("[bold cyan]Warming up ChatTTS model…[/bold cyan]")
        warmup_file = os.path.join(tempfile.gettempdir(), ".warmup_chattts.wav")
        try:
            await self.generate_audio("你好。", warmup_file)
            self.console.print("[green]ChatTTS model is ready.[/green]")
        except Exception as e:
            self.console.print("[bold yellow]Warning: ChatTTS warm-up failed.[/bold yellow]")
            logging.warning("ChatTTS warm-up failed: %s", e, exc_info=True)
        finally:
            if os.path.exists(warmup_file):
                try:
                    os.remove(warmup_file)
                except OSError:
                    pass
